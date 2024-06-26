import os.path
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional, Union

import pandas as pd
from torch.utils.data import DataLoader, Dataset
from tqdm.auto import tqdm

from DPF.configs import DatasetConfig, config2format
from DPF.connectors import Connector, LocalConnector
from DPF.dataloaders.dataloader_utils import (
    identical_collate_fn,
    identical_preprocess_function,
)
from DPF.datatypes import ColumnDataType
from DPF.filters import ColumnFilter, DataFilter
from DPF.modalities import MODALITIES, ModalityName
from DPF.processors.writers import ABSWriter, ShardedFilesWriter, ShardsWriter
from DPF.types import ModalityToDataMapping
from DPF.validators import ValidationResult


class DatasetProcessor(ABC):
    """DatasetProcessor is an interface used to interact with dataset

    Attributes
    ----------
    connector: Connector
        Connector to read datasets from
    df: pd.DataFrame
        Dataframe with dataset samples
    config: DatasetConfig
        Dataset config of type DatasetConfig
    """

    def __init__(
        self,
        connector: Connector,
        df: pd.DataFrame,
        config: DatasetConfig,
    ):
        self.connector = connector
        self._df = df
        self.config = config

    @property
    def df(self) -> pd.DataFrame:
        """Dataframe with dataset samples"""
        return self._df

    @property
    def columns(self) -> list[str]:
        """Columns that presented in dataframe"""
        return self._df.columns.tolist()  # type: ignore

    @property
    def modalities(self) -> list[str]:
        return list(self.config.modality2datatype.keys())

    def __getitem__(self, column_name: str) -> pd.Series:
        return self._df[column_name]

    def __setitem__(self, key: str, value: Union[list[str], pd.Series]) -> None:
        self._df[key] = value

    def print_summary(self) -> None:
        """Prints summary info about dataset"""
        print('Dataset format:', config2format(self.config))
        print('Path:', self.config.path)
        print('Modalities:', self.modalities)

        cols = self.columns
        print('Columns:', len(cols))
        last_s = f'Total samples: {len(self.df)}'
        print(last_s)

        width_columns = ['width', 'WIDTH', 'w']
        width_col = None
        for col in width_columns:
            if col in cols:
                width_col = col
                break
        height_columns = ['height', 'HEIGHT', 'h']
        height_col = None
        for col in height_columns:
            if col in cols:
                height_col = col
                break
        if width_col is not None and height_col is not None:
            data_width = self.df[width_col].describe()
            data_height = self.df[height_col].describe()
            data_aspect_ratio = (self.df[width_col]/self.df[height_col]).describe()
            data_aspect_ratio = {k:round(v, 2) for k,v in data_aspect_ratio.to_dict().items()}
            print('-'*len(last_s))
            print('width:', {k:round(v, 2) for k,v in data_width.to_dict().items()})
            print('height:', {k:round(v, 2) for k,v in data_height.to_dict().items()})
            last_s = f'aspect ratio: {data_aspect_ratio}'
            print(last_s)
            print('-'*len(last_s))

    @abstractmethod
    def rename_columns(self, column_map: dict[str, str], workers: int = 16) -> list[str]:
        """Renames columns in files of a dataset

        Parameters
        ----------
        column_map: Dict[str, str]
            Mapping of old column name into new column name
        workers: int = 16
            Number of parallel threads

        Returns
        -------
        List[str]
            List of errors
        """
        pass

    @abstractmethod
    def delete_columns(self, columns: list[str], workers: int = 16) -> list[str]:
        """Deletes columns in files of a dataset

        Parameters
        ----------
        columns: List[str]
            List of column names to delete
        workers: int = 16
            Number of parallel threads

        Returns
        -------
        List[str]
            List of errors
        """
        pass

    @abstractmethod
    def update_columns(self, columns: list[str], workers: int = 16) -> list[str]:
        """Updates info in columns or adds new columns in files of a dataset

        Parameters
        ----------
        columns: List[str]
            List of column names to add or update
        workers: int = 16
            Number of parallel threads

        Returns
        -------
        List[str]
            List of errors
        """
        pass

    @abstractmethod
    def _get_torch_dataset(
        self,
        modalities: list[ModalityName],
        columns_to_use: Optional[list[str]] = None,
        preprocess_f: Callable[[ModalityToDataMapping, dict[str, str]], Any] = identical_preprocess_function,
        return_none_on_error: bool = False
    ) -> Dataset[tuple[bool, Any]]:
        """Method that returns torch.Dataset class for this dataset"""
        pass

    def apply_data_filter(
        self,
        datafilter: DataFilter,
        validate_filter_result: bool = True,
        return_none_on_error: bool = False
    ) -> None:
        """Applies a data filter to dataset

        Parameters
        ----------
        datafilter: DataFilter
            Instance of a DataFilter
        validate_filter_result: bool = True
            Whether to check the correctness of datafilter result (data integrity)
        return_none_on_error: bool = False
            Whether to return None on sample if there is error in dataloader
        """
        dataset = self._get_torch_dataset(
            modalities=datafilter.modalities,
            columns_to_use=datafilter.metadata_columns + [datafilter.key_column],
            preprocess_f=datafilter.preprocess_data,
            return_none_on_error=return_none_on_error
        )
        df_result = datafilter.run(dataset)

        if validate_filter_result:
            assert set(self._df[datafilter.key_column]) == set(df_result[datafilter.key_column]), \
                f"Result dataframe after filter have different values in key column {datafilter.key_column}"
            assert len(df_result) == len(self._df), \
                f"Length of resulted dataframe changed after filtering. Old length = {len(self._df)}, new = {len(df_result)}"

        self._df = pd.merge(self._df, df_result, on=datafilter.key_column, how='left')

    def apply_multi_gpu_data_filter(  # type: ignore
        self,
        multi_gpu_datafilter,
        validate_filter_result: bool = True,
        return_none_on_error: bool = False
    ) -> None:
        """Applies a multi-gpu data filter to dataset

        Parameters
        ----------
        multi_gpu_datafilter: MultiGPUDataFilter
            Instance of a MultiGPUDataFilter
        validate_filter_result: bool = True
            Whether to check the correctness of datafilter result (data integrity)
        return_none_on_error: bool = False
            Whether to return None on sample if there is error in dataloader
        """
        self._df = multi_gpu_datafilter.run(
            self.df, self.config, self.connector,
            filter_run_kwargs={
                "validate_filter_result": validate_filter_result,
                "return_none_on_error": return_none_on_error
            }
        )

    def apply_column_filter(self, column_filter: ColumnFilter, validate_filter_result: bool = True) -> None:
        """Applies a column filter to dataset

        Parameters
        ----------
        column_filter: ColumnFilter
            Instance of a DataFilter
        validate_filter_result: bool = True
            Whether to check the correctness of datafilter result (data integrity)
        """
        filter_res = column_filter(self._df)

        if validate_filter_result:
            assert len(filter_res) == len(self._df), \
                f"Length of resulted dataframe changed after filtering. Old length = {len(self._df)}, new = {len(filter_res)}"

        if len(column_filter.schema) == 1:
            self._df[column_filter.schema[0]] = filter_res
        else:
            self._df[column_filter.schema] = filter_res

    @abstractmethod
    def validate(
        self,
        validate_filestructure: bool = True,
        validate_metadata: bool = True,
        columns_to_check: Optional[list[str]] = None,
        workers: int = 1,
        pbar: bool = True
    ) -> ValidationResult:
        """Validates a dataset to match the data format

        Parameters
        ----------
        validate_filestructure: bool = True
            Whether to validate the filestructure of a dataset
        validate_metadata: bool = True
            Whether to validate the metadata (or dataframes) of a dataset
        columns_to_check: Optional[List[str]] = None
            List of column names that should be in a dataset
        workers: int = 1
            Number of parallel threads for validation
        pbar: bool = True
            Whether to show progress bar or not

        Returns
        -------
        ValidationResult
            A dataclass with all validation errors
        """
        pass

    @abstractmethod
    def _read_sample_data(
        self,
        sample: dict[str, Any]
    ) -> ModalityToDataMapping:
        """Reads data for one sample from dataset

        Parameters
        ----------
        sample: dict[str, Any]
            Sample from dataframe

        Returns
        -------
        ModalityToDataMapping
            Mapping from modality name to its data
        """
        pass

    def get_random_sample(
        self,
        df_filter: Optional[pd.Series] = None
    ) -> tuple[ModalityToDataMapping, dict[str, Any]]:
        """Returns a random sample from dataset

        Parameters
        ----------
        df_filter: Optional[pd.Series] = None
            Condition for dataframe to filter, df[df_filter] will be used for sampling. If None, uses original dataframe.

        Returns
        -------
        ModalityToDataMapping
            Mapping from modality name to its data
        Dict[str, Any]
            Mapping from column name to its value
        """
        if df_filter is not None:
            df_to_sample = self.df[df_filter]
        else:
            df_to_sample = self.df

        sample = df_to_sample.sample(1).iloc[0].to_dict()
        modality2bytes = self._read_sample_data(sample)
        return modality2bytes, sample

    def filter_df(
        self,
        condition: pd.Series
    ) -> None:
        """Applies a condition filter for DataFrame (df attribute)

        Parameters
        ----------
        condition: pd.Series
            Condition for dataframe to filter. self.df = self.df[condition] will be used
        """
        self._df = self._df[condition]

    def _write_dataset(
        self,
        writer: ABSWriter,
        columns_to_save: Optional[list[str]] = None,
        dataloader_kwargs: Optional[dict[str, Any]] = None,
        pbar: bool = True
    ) -> None:
        columns_to_save = columns_to_save or []
        dataloader_kwargs = dataloader_kwargs or {}

        new_dataloader_kwargs = {
            'num_workers': 8,
            'batch_size': 1,
            'collate_fn': identical_collate_fn,
            'drop_last': False,
        }
        new_dataloader_kwargs.update(dataloader_kwargs)

        dataset = self._get_torch_dataset(
            list(self.config.modality2datatype.keys()),
            preprocess_f=identical_preprocess_function,
            columns_to_use=columns_to_save
        )
        dataloader = DataLoader(dataset, **new_dataloader_kwargs)  # type: ignore [arg-type]

        with writer as writer:
            for batch in tqdm(dataloader, disable=not pbar):
                modality2bytes, metadata = batch[0][1]

                modality2sample_data = {}
                for modality, bytes_data in modality2bytes.items():
                    datatype = self.config.modality2datatype[modality]
                    if isinstance(datatype, ColumnDataType):
                        pass
                    else:
                        path_col = MODALITIES[modality].path_column
                        extension = os.path.splitext(os.path.basename(metadata[path_col]))[-1]
                        modality2sample_data[modality] = (extension, bytes_data)
                        metadata.pop(path_col)

                writer.save_sample(modality2sample_data, metadata)

    def save_to_sharded_files(
        self,
        destination_dir: str,
        connector: Optional[Connector] = None,
        max_files_in_shard: int = 1000,
        datafiles_ext: str = "csv",
        filenaming: str = "counter",
        columns_to_save: Optional[list[str]] = None,
        rename_columns: Optional[dict[str, str]] = None,
        workers: int = 8,
        pbar: bool = True
    ) -> None:
        """Converts dataset to sharded files format

        Parameters
        ----------
        destination_dir: str
            Path to directory
        connector: Optional[Connector] = None
            The connector for where this path is located. LocalConnector is used by default
        max_files_in_shard: int = 1000
            Maximum number of files in shard
        datafiles_ext: str = "csv"
            Extension of files with data tables
        filenaming: str = "counter"
            File naming type. "counter" and "uuid" are available
        columns_to_save: Optional[List[str]] = None
            Column names to write in new dataset
        rename_columns: Optional[Dict[str, str]] = None
            Mapping used to rename columns
        workers: int = 8
            Number of parallel processes
        pbar: bool = True
            Whether to show a progress bar
        """
        if connector is None:
            connector = LocalConnector()

        writer = ShardedFilesWriter(
            connector,
            destination_dir,
            keys_mapping=rename_columns,
            max_files_in_shard=max_files_in_shard,
            datafiles_ext=datafiles_ext,
            filenaming=filenaming
        )
        self._write_dataset(
            writer,
            columns_to_save=columns_to_save,
            dataloader_kwargs={'num_workers': workers},
            pbar=pbar
        )

    def save_to_shards(
        self,
        destination_dir: str,
        connector: Optional[Connector] = None,
        max_files_in_shard: int = 1000,
        datafiles_ext: str = "csv",
        archives_ext: str = "tar",
        filenaming: str = "counter",
        columns_to_save: Optional[list[str]] = None,
        rename_columns: Optional[dict[str, str]] = None,
        workers: int = 8,
        pbar: bool = True
    ) -> None:
        """Converts dataset to sharded files format

        Parameters
        ----------
        destination_dir: str
            Path to directory
        connector: Optional[Connector] = None
            The connector where this path is located. LocalConnector is used by default
        max_files_in_shard: int = 1000
            Maximum number of files in shard
        datafiles_ext: str = "csv"
            Extension of files with data tables
        archives_ext: Optional[str] = "tar"
            Extension of archives with data
        filenaming: str = "counter"
            File naming type. "counter" and "uuid" are available
        columns_to_save: Optional[List[str]] = None
            Column names to write in new dataset
        rename_columns: Optional[Dict[str, str]] = None
            Mapping used to rename columns
        workers: int = 8
            Number of parallel processes
        pbar: bool = True
            Whether to show a progress bar
        """
        if connector is None:
            connector = LocalConnector()

        writer = ShardsWriter(
            connector,
            destination_dir,
            keys_to_rename=rename_columns,
            max_files_in_shard=max_files_in_shard,
            datafiles_ext=datafiles_ext,
            archives_ext=archives_ext,
            filenaming=filenaming
        )
        self._write_dataset(
            writer,
            columns_to_save=columns_to_save,
            dataloader_kwargs={'num_workers': workers},
            pbar=pbar
        )

    def __len__(self) -> int:
        return len(self.df)
