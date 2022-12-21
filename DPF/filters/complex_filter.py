from typing import List, Union, Optional
import os
import pandas as pd
from PIL import Image
from tqdm import tqdm

from DPF.dataloaders.images import UniversalT2IDataloader
from DPF.filters.images.img_filter import ImageFilter
from DPF.filters.text2image.t2ifilter import T2IFilter
from DPF.filesystems.filesystem import FileSystem


allowed_filter_types = (T2IFilter, ImageFilter)

class ComplexFilter(ImageFilter):
    def __init__(
            self, 
            filter_list: List[Union[ImageFilter, T2IFilter]], 
            use_same_preprocess: bool = False,
            task_name: Optional[str] = None, save_parquets_dir: Optional[str] = None, 
            save_parquets: bool = False, pbar: bool = True, workers: int = 16
        ):
        super(ComplexFilter, self).__init__(task_name, save_parquets, save_parquets_dir, pbar)
        
        self.filter_list = filter_list
        self.num_workers = workers
        self.use_same_preprocess = use_same_preprocess
        
        assert len(filter_list) > 0, "There should be at list one filter"
        assert all([isinstance(f, allowed_filter_types) for f in self.filter_list]), \
            f"All filters should be instances of classes: {allowed_filter_types}"
        
        self.batch_size = max([f.dataloader_kwargs["batch_size"] for f in self.filter_list])
        
        self.columns_to_return_for_dataloader = set()
        for f in filter_list:
            if 'cols_to_return' in f.dataloader_kwargs:
                self.columns_to_return_for_dataloader.update(set(f.dataloader_kwargs["cols_to_return"]))
        self.columns_to_return_for_dataloader = list(self.columns_to_return_for_dataloader)
        
        self.schema = []
        for f in filter_list:
            cols = [colname for colname in f.schema if colname != "image_path"]
            for colname in f.schema:
                if colname != "image_path":
                    assert colname not in self.schema, \
                        f"Several filters have same output column: {colname}"
                    self.schema.append(colname)
        self.schema = ["image_path"]+list(self.schema)
        
        self.dataloader_kwargs = dict(
            num_workers=self.num_workers, batch_size=self.batch_size,
            preprocess_f=self.preprocess, collate_fn=lambda x: x,
            drop_last=False, cols_to_return=self.columns_to_return_for_dataloader
        )
        
    def preprocess(self, img_bytes: bytes, data: dict):
        preprocessed_data = []
        
        if self.use_same_preprocess:
            preprocessed_data.append(self.filter_list[0].preprocess(img_bytes, data))
        else:
            for imgfilter in self.filter_list:
                preprocessed_data.append(imgfilter.preprocess(img_bytes, data))
                
        return preprocessed_data
        
    @staticmethod
    def _add_values_from_batch(main_dict: dict, batch_dict: dict):
        for k, v in batch_dict.items():
            main_dict[k].extend(v)
        
    def run(self, df: pd.DataFrame, filesystem: FileSystem) -> pd.DataFrame:
        dataloader = UniversalT2IDataloader(filesystem, df, **self.dataloader_kwargs)
        
        df_labels = self._generate_dict_from_schema()
        
        for batch in tqdm(dataloader, disable=not self.pbar):
            for c, imgfilter in enumerate(self.filter_list):
                filter_bs = imgfilter.dataloader_kwargs["batch_size"]
                
                if self.use_same_preprocess:
                    data_for_filter = [item[0] for item in batch]
                else:
                    data_for_filter = [item[c] for item in batch]
                
                for i in range(0, len(data_for_filter), filter_bs):
                    batch_for_filter = data_for_filter[i:i+filter_bs]
                    df_batch_labels = imgfilter.process_batch(batch_for_filter)
                    # save 'image_path' column only one time
                    if c > 0:
                        df_batch_labels.pop('image_path')
                    self._add_values_from_batch(df_labels, df_batch_labels)

        df_result = pd.DataFrame(df_labels)
        df = pd.merge(df, df_result, on='image_path')
        
        if self.save_parquets:
            parquet_path = f'{self.save_parquets_dir}/{self.task_name}.parquet'
            df.to_parquet(
                parquet_path,
                index=False
            )
        
        return df
    
    def __call__(self, df: pd.DataFrame, filesystem: FileSystem) -> pd.DataFrame:
        return self.run(df, filesystem)