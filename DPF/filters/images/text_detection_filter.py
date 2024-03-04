from typing import Dict, List, Union, Any
import numpy as np

from DPF.utils import read_image_rgb_from_bytes
from .img_filter import ImageFilter

from CRAFT import CRAFTModel, preprocess_image, boxes_area


class CRAFTFilter(ImageFilter):

    def __init__(
        self,
        weights_folder: str,
        use_refiner: bool = False,
        device: str = "cuda:0",
        workers: int = 16,
        pbar: bool = True,
    ):
        super().__init__(pbar)

        self.num_workers = workers
        self.batch_size = 1
        self.device = device

        self.weights_folder = weights_folder
        self.model = CRAFTModel(weights_folder, device, use_refiner=False, fp16=True)

    @property
    def schema(self) -> List[str]:
        return [self.key_column, "text_boxes", "num_text_boxes", "text_area"]

    @property
    def dataloader_kwargs(self) -> Dict[str, Any]:
        return {
            "num_workers": self.num_workers,
            "batch_size": self.batch_size,
            "drop_last": False,
        }

    def preprocess(self, modality2data: Dict[str, Union[bytes, str]], metadata: dict):
        key = metadata[self.key_column]
        pil_img = read_image_rgb_from_bytes(modality2data['image'])
        img_tensor, ratio_w, ratio_h = preprocess_image(np.array(pil_img), self.model.canvas_size, self.model.mag_ratio)
        return key, img_tensor, ratio_w, ratio_h, pil_img.size

    def process_batch(self, batch) -> dict:
        df_batch_labels = self._generate_dict_from_schema()
        
        key, img_tensor, ratio_w, ratio_h, orig_size = batch[0]

        boxes = self.model._get_boxes_preproc(img_tensor, ratio_w, ratio_h)
        df_batch_labels["text_boxes"].append(boxes)
        df_batch_labels["num_text_boxes"].append(len(boxes))
        df_batch_labels["text_area"].append(boxes_area(boxes)/(orig_size[0]*orig_size[1]))
        df_batch_labels[self.key_column].append(key)

        return df_batch_labels
