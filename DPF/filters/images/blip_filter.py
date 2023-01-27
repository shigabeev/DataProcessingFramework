from .img_filter import ImageFilter
from PIL import Image
import torch
import urllib
import os
import sys
from lavis.models import load_model_and_preprocess
from DPF.utils import read_image_rgb_from_bytes
from DPF.filters.utils import FP16Module, identical_collate_fn
from torchvision import transforms
from torchvision.transforms.functional import InterpolationMode

try:
    from torch.utils.data.dataloader import default_collate
except ImportError:
    from torch.utils.data import default_collate


class BLIPFilter(ImageFilter):

    def __init__(self, task_name=None, save_parquets_dir=None,
                 save_parquets=False, pbar=True, workers=16, batch_size=64, device='cuda:0'):
        super(BLIPFilter, self).__init__(task_name, save_parquets, save_parquets_dir, pbar)

        self.num_workers = workers
        self.batch_size = batch_size
        self.device = device
        
        self.blip_model, self.blip_processor, _ = load_model_and_preprocess(name="blip_caption", model_type="base_coco",
                                                                             is_eval=True, device=self.device)
        self.blip_processor = self.blip_processor["eval"]

        self.schema = ['image_path', 'blip_caption']
        self.dataloader_kwargs = dict(
            num_workers=self.num_workers, batch_size=self.batch_size,
            preprocess_f=self.preprocess, collate_fn=identical_collate_fn,
            drop_last=False
        )

    def preprocess(self, img_bytes, data):
        image_path = data['image_path']
        pil_img = read_image_rgb_from_bytes(img_bytes)
        img_tensor = self.blip_processor(pil_img)
        return image_path, img_tensor

    def process_batch(self, batch) -> dict:
        df_batch_labels = self._generate_dict_from_schema()

        image_paths, image_tensors = list(zip(*batch))

        with torch.no_grad():
            batch = default_collate(image_tensors).to(self.device)
            captions = self.blip_model.generate({'image': batch})

        df_batch_labels['blip_caption'].extend(captions)
        df_batch_labels['image_path'].extend(image_paths)

        return df_batch_labels