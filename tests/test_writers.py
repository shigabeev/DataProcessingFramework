import os
import shutil

from DPF import DatasetReader
from DPF.configs import (
    FilesDatasetConfig,
    ShardedFilesDatasetConfig,
    ShardsDatasetConfig,
)


def test_shards_to_shards():
    path = 'tests/datasets/shards_correct'
    config = ShardsDatasetConfig.from_path_and_columns(
        path,
        image_name_col="image_name",
        text_col="caption"
    )

    reader = DatasetReader()
    processor = reader.read_from_config(config)
    new_dir = 'test_shards/'
    if os.path.exists(new_dir):
        shutil.rmtree(new_dir)
    processor.save_to_shards(
        new_dir,
        rename_columns={'text': 'caption'},
        workers=1
    )

    config = ShardsDatasetConfig.from_path_and_columns(
        new_dir.rstrip('/'),
        image_name_col="image_name",
        text_col="caption"
    )

    reader = DatasetReader()
    processor = reader.read_from_config(config)
    result = processor.validate()
    assert result.total_errors == 0

    if os.path.exists(new_dir):
        shutil.rmtree(new_dir)


def test_shards_to_sharded_files():
    path = 'tests/datasets/shards_correct'
    config = ShardsDatasetConfig.from_path_and_columns(
        path,
        image_name_col="image_name",
        text_col="caption"
    )

    reader = DatasetReader()
    processor = reader.read_from_config(config)
    new_dir = 'test_sharded_files/'
    if os.path.exists(new_dir):
        shutil.rmtree(new_dir)
    processor.save_to_sharded_files(
        new_dir,
        rename_columns={'text': 'caption'},
        workers=1
    )

    config = ShardedFilesDatasetConfig.from_path_and_columns(
        new_dir.rstrip('/'),
        image_name_col="image_name",
        text_col="caption"
    )

    reader = DatasetReader()
    processor = reader.read_from_config(config)
    result = processor.validate()
    assert result.total_errors == 0

    if os.path.exists(new_dir):
        shutil.rmtree(new_dir)


def test_files_to_shards():
    path = 'tests/datasets/files_correct/data.csv'
    config = FilesDatasetConfig.from_path_and_columns(
        path,
        image_path_col="image_path",
        text_col="caption"
    )

    reader = DatasetReader()
    processor = reader.read_from_config(config)
    new_dir = 'test_shards/'
    if os.path.exists(new_dir):
        shutil.rmtree(new_dir)
    processor.save_to_shards(
        new_dir.rstrip('/'),
        rename_columns={'text': 'caption'},
        workers=1
    )

    config = ShardsDatasetConfig.from_path_and_columns(
        new_dir.rstrip('/'),
        image_name_col="image_name",
        text_col="caption"
    )

    reader = DatasetReader()
    processor = reader.read_from_config(config)
    result = processor.validate()
    assert result.total_errors == 0

    if os.path.exists(new_dir):
        shutil.rmtree(new_dir)


def test_files_to_sharded_files():
    path = 'tests/datasets/files_correct/data.csv'
    config = FilesDatasetConfig.from_path_and_columns(
        path,
        image_path_col="image_path",
        text_col="caption"
    )

    reader = DatasetReader()
    processor = reader.read_from_config(config)
    new_dir = 'test_sharded_files/'
    if os.path.exists(new_dir):
        shutil.rmtree(new_dir)
    processor.save_to_sharded_files(
        new_dir.rstrip('/'),
        rename_columns={'text': 'caption'},
        workers=1
    )

    config = ShardedFilesDatasetConfig.from_path_and_columns(
        new_dir.rstrip('/'),
        image_name_col="image_name",
        text_col="caption"
    )

    reader = DatasetReader()
    processor = reader.read_from_config(config)
    result = processor.validate()
    assert result.total_errors == 0

    if os.path.exists(new_dir):
        shutil.rmtree(new_dir)
