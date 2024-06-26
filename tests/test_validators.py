from DPF import DatasetReader
from DPF.configs import (
    FilesDatasetConfig,
    ShardedFilesDatasetConfig,
    ShardsDatasetConfig,
)
from DPF.validators.errors import IsNotKeyError, MissedColumnsError, MissingValueError


def test_shards_reader():
    path = 'tests/datasets/shards_correct'
    config = ShardsDatasetConfig.from_path_and_columns(
        path,
        image_name_col="image_name",
        text_col="caption"
    )

    reader = DatasetReader()
    processor = reader.read_from_config(config)

    result = processor.validate()
    assert result.total_errors == 0


def test_shards_wrong_columns():
    path = 'tests/datasets/shards_wrong_columns'
    config = ShardsDatasetConfig.from_path_and_columns(
        path,
        image_name_col="image_name",
        text_col="caption"
    )

    reader = DatasetReader()
    processor = reader.read_from_config(config, validate_columns=False)

    result = processor.validate()
    assert len(result.metadata_errors) == 0
    assert len(result.filestructure_errors) == 1
    assert isinstance(result.filestructure_errors[0], IsNotKeyError)

    result = processor.validate(columns_to_check=['image_name', 'caption', 'test'])
    assert len(result.metadata_errors) == 1
    assert isinstance(result.metadata_errors[path + '/0.csv'][0], MissedColumnsError)
    assert len(result.filestructure_errors) == 1
    assert isinstance(result.filestructure_errors[0], IsNotKeyError)


def test_shards_wrong_tar():
    path = 'tests/datasets/shards_wrong_tar'
    config = ShardsDatasetConfig.from_path_and_columns(
        path,
        image_name_col="image_name",
        text_col="caption"
    )
    reader = DatasetReader()
    processor = reader.read_from_config(config)

    result = processor.validate()

    print(result)
    assert len(result.metadata_errors) == 1
    assert isinstance(result.metadata_errors[path + '/0.csv'][0], MissingValueError)
    assert len(result.filestructure_errors) == 0


def test_sharded_files_reader():
    path = 'tests/datasets/sharded_files_correct'
    config = ShardedFilesDatasetConfig.from_path_and_columns(
        path,
        image_name_col="image_name",
        text_col="caption"
    )

    reader = DatasetReader()
    processor = reader.read_from_config(config)

    result = processor.validate()
    assert result.total_errors == 0


def test_sharded_files_wrong_columns():
    path = 'tests/datasets/sharded_files_wrong_columns'
    config = ShardedFilesDatasetConfig.from_path_and_columns(
        path,
        image_name_col="image_name",
        text_col="caption"
    )

    reader = DatasetReader()
    processor = reader.read_from_config(config, validate_columns=False)

    result = processor.validate()
    assert len(result.metadata_errors) == 0
    assert len(result.filestructure_errors) == 1
    assert isinstance(result.filestructure_errors[0], IsNotKeyError)

    result = processor.validate(columns_to_check=['image_name', 'caption', 'test'])
    assert len(result.metadata_errors) == 1
    assert isinstance(result.metadata_errors[path + '/0.csv'][0], MissedColumnsError)
    assert len(result.filestructure_errors) == 1
    assert isinstance(result.filestructure_errors[0], IsNotKeyError)


def test_sharded_files_wrong_tar():
    path = 'tests/datasets/sharded_files_wrong_folder'
    config = ShardedFilesDatasetConfig.from_path_and_columns(
        path,
        image_name_col="image_name",
        text_col="caption"
    )
    reader = DatasetReader()
    processor = reader.read_from_config(config)

    result = processor.validate()

    print(result)
    assert len(result.metadata_errors) == 1
    assert isinstance(result.metadata_errors[path + '/0.csv'][0], MissingValueError)
    assert len(result.filestructure_errors) == 0


def test_files_reader():
    path = 'tests/datasets/files_correct/data.csv'
    config = FilesDatasetConfig.from_path_and_columns(
        path,
        image_path_col="image_path",
        text_col="caption"
    )

    reader = DatasetReader()
    processor = reader.read_from_config(config)

    result = processor.validate()
    assert result.total_errors == 0
