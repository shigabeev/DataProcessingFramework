from abc import abstractmethod
import traceback
from typing import Optional, Dict, Tuple


class ABSWriter:
    @abstractmethod
    def save_sample(
        self,
        modality2sample_data: Dict[str, Tuple[str, bytes]],
        table_data: Dict[str, str] = {},
    ) -> None:
        pass

    @abstractmethod
    def __enter__(self) -> "ABSWriter":
        pass

    @abstractmethod
    def __exit__(
        self,
        exception_type,
        exception_value: Optional[Exception],
        exception_traceback: traceback,
    ) -> None:
        pass
