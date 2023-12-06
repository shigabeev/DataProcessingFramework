from typing import List, Dict, Optional, Callable, Any, Union
import pandas as pd
from torch.utils.data import Dataset

from DPF.filesystems.filesystem import FileSystem
from DPF.dataloaders.utils import default_preprocess
from DPF.datatypes import ShardedDataType, ColumnDataType, FileDataType


class FilesDataset(Dataset):
    """
    Dataset class to read "raw" files
    """

    def __init__(
        self,
        filesystem: FileSystem,
        df: pd.DataFrame,
        datatypes: List[Union[ShardedDataType, FileDataType, ColumnDataType]],
        meta_columns: Optional[List[str]] = None,
        preprocess_f: Callable[[Dict[str, bytes], Dict[str, str]], Any] = default_preprocess,
        return_none_on_error: bool = False
    ):
        """
        Parameters
        ----------
        filesystem: FileSystem
            Object of a DPF.filesystems.Filesystem type
        df: pd.DataFrame
            Dataset dataframe from DatasetProcessor
        datatypes: List[Union[ShardedDataType, FileDataType, ColumnDataType]]
            List of datatypes to read
        meta_columns: Optional[List[str]] = None
            List of dataframe columns to return from dataloader
        preprocess_f: Callable[[Dict[str, bytes], Dict[str, str]], Any] = default_preprocess
            Preprocessing function for data. First argument of the preprocess_f is mapping from modality name to bytes
            and the second argument is mapping from meta_column name to its value.
        return_none_on_error: bool = False
            Whether to return None if error during reading file occures
        """
        super(FilesDataset).__init__()
        self.filesystem = filesystem

        self.datatypes = datatypes
        self.meta_columns = meta_columns or []
        self.configure_columns()

        self.data_to_iterate = df[self.columns].values
        self.preprocess_f = preprocess_f
        self.return_none_on_error = return_none_on_error

    def configure_columns(self):
        self.path_column2modality = {}
        self.column2modality = {}
        for d in self.datatypes:
            if isinstance(d, ColumnDataType):
                self.column2modality[d.modality.column] = d.modality.key
            elif isinstance(d, (ShardedDataType, FileDataType)):
                self.path_column2modality[d.modality.path_column] = d.modality.key
            else:
                raise ValueError()
        self.columns = list(set(
            list(self.path_column2modality.keys()) + list(self.column2modality.keys()) + self.meta_columns
        ))

    def __len__(self):
        return len(self.data_to_iterate)

    def __getitem__(self, idx):
        data = {
            self.columns[c]: item for c, item in enumerate(self.data_to_iterate[idx])
        }
        modality2data = {}

        # read files
        for col in self.path_column2modality.keys():
            modality = self.path_column2modality[col]
            if self.return_none_on_error:
                try:
                    file_bytes = self.filesystem.read_file(data[col], binary=True).getvalue()
                except Exception as err:
                    file_bytes = None
            else:
                file_bytes = self.filesystem.read_file(data[col], binary=True).getvalue()
            modality2data[modality] = file_bytes

        # read data from columns
        for col in self.column2modality.keys():
            modality = self.column2modality[col]
            modality2data[modality] = data[col]

        return self.preprocess_f(modality2data, data)
