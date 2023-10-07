from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict

import pandas as pd
from tqdm.contrib.concurrent import thread_map

from DPF.validators.format_validators import (
    IsNotKeyError, FileStructureError, DataFrameError, MissedColumnsError, DuplicatedValuesError
)
from DPF.validators import Validator, ValidationResult
from DPF.datatypes import ShardedDataType
from DPF.filesystems import FileSystem
from DPF.configs import ShardedDatasetConfig


@dataclass
class ShardedValidationResult(ValidationResult):
    filestructure_errors: List[FileStructureError]
    dataframe_errors: Dict[str, List[DataFrameError]]

    def __repr__(self):
        s = "ShardedValidationResult:"
        s += f"\nfilestructure_errors = {self.filestructure_errors}"
        s += f"\ndataframe_errors = {self.dataframe_errors}"
        return s

    @property
    def total_errors(self) -> int:
        return len(self.filestructure_errors) + sum(map(len, self.dataframe_errors.values()))


class ShardedValidator(Validator, ABC):

    def __init__(
        self,
        merged_df: pd.DataFrame,
        filesystem: FileSystem,
        config: ShardedDatasetConfig,
        columns_to_check: List[str]
    ):
        self.merged_df = merged_df
        self.filesystem = filesystem
        self.config = config
        self.columns_to_check = columns_to_check

    @abstractmethod
    def _validate_files(self, filepaths: List[str]) -> List[FileStructureError]:
        pass

    def _validate_filestructure(self, filepaths: List[str]) -> List[FileStructureError]:
        errors = []

        for datatype in self.config.datatypes:
            if isinstance(datatype, ShardedDataType):
                has_duplicates = self.merged_df[datatype.modality.path_column].str.split('/').str[-1].duplicated().any()
                if has_duplicates:
                    errors.append(IsNotKeyError(datatype.user_basename_column_name))

        errors.extend(self._validate_files(filepaths))
        return errors

    @abstractmethod
    def _validate_shard_files(
        self,
        dataframe_path: str,
        df: pd.DataFrame
    ) -> (List[FileStructureError], List[DataFrameError]):
        pass

    def _validate_shard(self, path: str) -> (List[DataFrameError], List[FileStructureError]):
        df = self.filesystem.read_dataframe(path)
        errors = []

        missed_columns = set(self.columns_to_check).difference(set(df.columns))
        if len(missed_columns) > 0:
            errors.append(MissedColumnsError(path, list(missed_columns)))

        for datatype in self.config.datatypes:
            if isinstance(datatype, ShardedDataType):
                filenames = df[datatype.user_basename_column_name]
                has_duplicates = filenames.duplicated().any()
                if has_duplicates:
                    errors.append(DuplicatedValuesError(path, datatype.user_basename_column_name))

        filestructure_errors, df_errors = self._validate_shard_files(path, df)
        errors.extend(df_errors)
        return errors, filestructure_errors

    def _validate_dataframes(
        self,
        filepaths: List[str],
        threads: int = 16,
        pbar: bool = True
    ) -> (Dict[str, List[DataFrameError]], List[FileStructureError]):
        datafiles = [f for f in filepaths if f.endswith('.'+self.config.datafiles_ext)]

        results = thread_map(
            lambda x: (x, self._validate_shard(x)),
            datafiles,
            max_workers=threads,
            disable=not pbar
        )
        dataframe2errors = {}
        filestructure_errors = []
        for res in results:
            dataframe2errors[res[0]] = res[1][0]
            filestructure_errors.extend(res[1][1])
        return dataframe2errors, filestructure_errors

    def validate(
        self,
        validate_filestructure: bool = True,
        validate_dataframes: bool = True,
        threads: int = 16,
        pbar: bool = True
    ) -> ShardedValidationResult:
        filepaths = self.filesystem.listdir(self.config.path)
        filestructure_errors = []
        dataframe2errors = {}

        if validate_filestructure:
            filestructure_errors.extend(self._validate_filestructure(filepaths))

        if validate_dataframes:
            _dataframe2errors, _filestructure_errors = self._validate_dataframes(filepaths, threads, pbar)
            filestructure_errors.extend(_filestructure_errors)
            for path, errors in _dataframe2errors.items():
                if len(errors) > 0:
                    dataframe2errors[path] = errors

        return ShardedValidationResult(filestructure_errors, dataframe2errors)