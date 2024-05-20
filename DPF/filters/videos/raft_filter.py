import io
import os
from typing import Any
from urllib.request import urlopen
from zipfile import ZipFile

import cv2
import imageio.v3 as iio
import numpy as np
import torch
import torch.nn.functional as F
from cv2.typing import MatLike
from torch import Tensor

from ...types import ModalityToDataMapping
from .raft_core.model import RAFT
from .video_filter import VideoFilter

WEIGHTS_URL = 'https://dl.dropboxusercontent.com/s/4j4z58wuv8o0mfz/models.zip'


def transform_frame(frame: MatLike, target_size: tuple[int, int]) -> Tensor:
    frame = cv2.resize(frame, dsize=(target_size[0], target_size[1]), interpolation=cv2.INTER_LINEAR)
    frame_tensor = torch.from_numpy(frame).permute(2, 0, 1).float()[None]

    padder = InputPadder(frame_tensor.shape)  # type: ignore
    frame_tensor = padder.pad(frame_tensor)[0]
    return frame_tensor


class InputPadder:
    """ Pads images such that dimensions are divisible by 8 """

    def __init__(self, dims: list[int], mode: str = 'sintel'):
        self.ht, self.wd = dims[-2:]
        pad_ht = (((self.ht // 8) + 1) * 8 - self.ht) % 8
        pad_wd = (((self.wd // 8) + 1) * 8 - self.wd) % 8
        if mode == 'sintel':
            self._pad = [pad_wd // 2, pad_wd - pad_wd // 2,
                         pad_ht // 2, pad_ht - pad_ht // 2]
        else:
            self._pad = [pad_wd // 2, pad_wd - pad_wd // 2,
                         0, pad_ht]

    def pad(self, *inputs) -> list[Tensor]:  # type: ignore
        return [F.pad(x, self._pad, mode='replicate') for x in inputs]

    def unpad(self, x: Tensor) -> Tensor:
        ht, wd = x.shape[-2:]
        c = [self._pad[2], ht - self._pad[3], self._pad[0], wd - self._pad[1]]
        return x[..., c[0]:c[1], c[2]:c[3]]


class RAFTOpticalFlowFilter(VideoFilter):
    """
    RAFT model inference class to get mean optical flow each video.
        The video's current and next frame are used for optical flow calculation between them.
        After, the mean value of optical flow for the entire video is calculated on the array of optical flow between two frames.
    More info about the model here: https://github.com/princeton-vl/RAFT
    """

    def __init__(
        self,
        pass_frames: int = 10,
        use_small_model: bool = False,
        device: str = "cuda:0",
        workers: int = 16,
        batch_size: int = 1,
        pbar: bool = True,
        _pbar_position: int = 0
    ):
        super().__init__(pbar, _pbar_position)
        self.num_workers = workers
        self.batch_size = batch_size
        self.device = device

        assert pass_frames >= 1, "Number of pass_frames should be greater or equal to 1."
        self.pass_frames = pass_frames

        resp = urlopen(WEIGHTS_URL)
        zipped_files = ZipFile(io.BytesIO(resp.read()))

        if use_small_model:
            self.model_name = "raft_small"
            model_weights_path = os.path.join("models", "raft-small.pth")
        else:
            self.model_name = "raft"
            model_weights_path = os.path.join("models", "raft-things.pth")

        self.model = RAFT(small=use_small_model)

        model_weights = torch.load(zipped_files.open(model_weights_path))
        model_weights = {key.replace("module.", ""): value for key, value in model_weights.items()}
        self.model.load_state_dict(model_weights)

        self.model.to(self.device)
        self.model.eval()

    @property
    def result_columns(self) -> list[str]:
        return [f"mean_optical_flow_{self.model_name}"]

    @property
    def dataloader_kwargs(self) -> dict[str, Any]:
        return {
            "num_workers": self.num_workers,
            "batch_size": self.batch_size,
            "drop_last": False,
        }

    def preprocess_data(
        self,
        modality2data: ModalityToDataMapping,
        metadata: dict[str, Any]
    ) -> Any:
        key = metadata[self.key_column]
        video_file = modality2data['video']

        frames = iio.imread(io.BytesIO(video_file), plugin="pyav")

        if frames.shape[1] > frames.shape[2]:
            frames_resized = [
                transform_frame(frame=frames[i], target_size=(450, 800))
                for i in range(self.pass_frames, len(frames), self.pass_frames)
            ]
        elif frames.shape[2] > frames.shape[1]:
            frames_resized = [
                transform_frame(frame=frames[i], target_size=(800, 450))
                for i in range(self.pass_frames, len(frames), self.pass_frames)
            ]
        else:
            frames_resized = [
                transform_frame(frame=frames[i], target_size=(450, 450))
                for i in range(self.pass_frames, len(frames), self.pass_frames)
            ]
        return key, frames_resized

    def process_batch(self, batch: list[Any]) -> dict[str, list[Any]]:
        df_batch_labels = self._get_dict_from_schema()

        mean_magnitudes: list[float] = []
        for data in batch:
            key, frames = data
            with torch.no_grad():
                for i in range(self.pass_frames, len(frames), self.pass_frames):
                    current_frame = frames[i - self.pass_frames]
                    next_frame = frames[i]

                    if (i - self.pass_frames) == 0:
                        current_frame_cuda = current_frame.to(self.device)
                        next_frame_cuda = next_frame.to(self.device)

                        _, flow = self.model(
                            current_frame_cuda,
                            next_frame_cuda,
                            iters=20, test_mode=True
                        )
                    else:
                        current_frame_cuda = next_frame_cuda
                        next_frame_cuda = next_frame.to(self.device)

                        _, flow = self.model(
                            current_frame_cuda,
                            next_frame_cuda,
                            iters=20, test_mode=True
                        )

                    flow = flow.detach().cpu().numpy()
                    magnitude, angle = cv2.cartToPolar(flow[0][..., 0], flow[0][..., 1])
                    mean_magnitudes.append(magnitude)
                mean_value = np.mean(mean_magnitudes)

                df_batch_labels[self.key_column].append(key)
                df_batch_labels[self.schema[1]].append(round(mean_value, 3))
        return df_batch_labels