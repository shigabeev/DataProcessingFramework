from typing import List, Dict, Optional, Union
from abc import abstractmethod

from DPF.datatypes import DataType


# TODO(review) - отнаследовать класс от ABC, чтобы класс был абстрактным 
class DatasetConfig:
    """Config for a dataset"""

    def __init__(
        self,
        path: str,
        datatypes: List[DataType],
    ):
        """
        Parameters
        ----------
        path: str
            Path to dataset
        datatypes: List[DataType]
            List of datatypes in dataset
        """
        assert len(set([d.modality.key for d in datatypes])) == len(datatypes)
        self.datatypes = datatypes
        # TODO(review) - обрезание пути справа, надо сделать проверку на корректность пути, либо его парсить и его собирать заново
        self.path = path.rstrip('/')

    @property
    @abstractmethod
    def modality2datatype(self) -> Dict[str, DataType]:
        pass

    @property
    @abstractmethod
    def columns_mapping(self) -> Dict[str, str]:
        pass

    def __repr__(self) -> str:
        s = "DatasetConfig(\n\t"
        s += 'datatypes=[\n\t\t'
        s += '\n\t\t'.join([str(i) for i in self.datatypes])
        s += '\n\t]'
        s += '\n)'
        return s