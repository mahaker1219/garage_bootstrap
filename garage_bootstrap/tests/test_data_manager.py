"""
Tests for data manager module.
"""

import io
import json
import os
import tarfile
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from garage_bootstrap.data_manager import DataManager


class TestDataManager:
    """Tests for DataManager class."""

    @patch("boto3.client")
    def test_init(self, mock_boto):
        """Test DataManager initialization."""
        manager = DataManager(
            endpoint="localhost:3900",
            access_key="test-key",
            secret_key="test-secret",
        )

        mock_boto.assert_called_once()
        assert manager.endpoint == "http://localhost:3900"

    @patch("boto3.client")
    def test_list_buckets(self, mock_boto):
        """Test listing buckets."""
        mock_client = MagicMock()
        mock_client.list_buckets.return_value = {
            "Buckets": [{"Name": "bucket1"}, {"Name": "bucket2"}]
        }
        mock_boto.return_value = mock_client

        manager = DataManager(
            endpoint="localhost:3900",
            access_key="test-key",
            secret_key="test-secret",
        )

        buckets = manager.list_buckets()

        assert buckets == ["bucket1", "bucket2"]

    @patch("boto3.client")
    def test_get_object(self, mock_boto):
        """Test getting an object."""
        mock_body = MagicMock()
        mock_body.read.return_value = b"test-content"

        mock_client = MagicMock()
        mock_client.get_object.return_value = {
            "Body": mock_body,
            "ContentType": "text/plain",
            "Metadata": {"key": "value"},
            "ETag": '"abc123"',
        }
        mock_boto.return_value = mock_client

        manager = DataManager(
            endpoint="localhost:3900",
            access_key="test-key",
            secret_key="test-secret",
        )

        data, metadata = manager.get_object("test-bucket", "test-key")

        assert data == b"test-content"
        assert metadata["ContentType"] == "text/plain"

    @patch("boto3.client")
    def test_put_object(self, mock_boto):
        """Test putting an object."""
        mock_client = MagicMock()
        mock_client.put_object.return_value = {"ETag": '"abc123"'}
        mock_boto.return_value = mock_client

        manager = DataManager(
            endpoint="localhost:3900",
            access_key="test-key",
            secret_key="test-secret",
        )

        etag = manager.put_object("test-bucket", "test-key", b"test-data")

        assert etag == "abc123"
        mock_client.put_object.assert_called_once()

    @patch("boto3.client")
    def test_delete_object(self, mock_boto):
        """Test deleting an object."""
        mock_client = MagicMock()
        mock_boto.return_value = mock_client

        manager = DataManager(
            endpoint="localhost:3900",
            access_key="test-key",
            secret_key="test-secret",
        )

        result = manager.delete_object("test-bucket", "test-key")

        assert result is True
        mock_client.delete_object.assert_called_with(Bucket="test-bucket", Key="test-key")


class TestExportImport:
    """Tests for export and import functionality."""

    @patch("boto3.client")
    def test_export_to_directory(self, mock_boto, tmp_path):
        """Test exporting bucket to directory."""
        mock_body = MagicMock()
        mock_body.read.return_value = b"file-content"

        mock_client = MagicMock()

        # Mock paginator
        mock_paginator = MagicMock()
        mock_page = {
            "Contents": [
                {
                    "Key": "file1.txt",
                    "Size": 12,
                    "ETag": '"abc"',
                    "LastModified": MagicMock(),
                }
            ]
        }
        mock_paginator.paginate.return_value = [mock_page]
        mock_client.get_paginator.return_value = mock_paginator

        mock_client.get_object.return_value = {
            "Body": mock_body,
            "ContentType": "text/plain",
            "Metadata": {},
            "ETag": '"abc"',
        }
        mock_boto.return_value = mock_client

        manager = DataManager(
            endpoint="localhost:3900",
            access_key="test-key",
            secret_key="test-secret",
        )

        output_dir = tmp_path / "export"
        result = manager.export_to_directory("test-bucket", str(output_dir))

        assert result["exported"] == 1
        assert (output_dir / "file1.txt").exists()
        assert (output_dir / "_manifest.json").exists()

    @patch("boto3.client")
    def test_import_from_directory(self, mock_boto, tmp_path):
        """Test importing from directory to bucket."""
        # Create test files
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        subdir = tmp_path / "subdir"
        subdir.mkdir()
        nested_file = subdir / "nested.txt"
        nested_file.write_text("nested content")

        mock_client = MagicMock()
        mock_client.put_object.return_value = {"ETag": '"abc"'}
        mock_boto.return_value = mock_client

        manager = DataManager(
            endpoint="localhost:3900",
            access_key="test-key",
            secret_key="test-secret",
        )

        result = manager.import_from_directory("test-bucket", str(tmp_path))

        assert result["imported"] == 2
        assert mock_client.put_object.call_count == 2

    @patch("boto3.client")
    def test_export_bucket_archive(self, mock_boto, tmp_path):
        """Test exporting bucket to tar.gz archive."""
        mock_body = MagicMock()
        mock_body.read.return_value = b"file-content"

        mock_client = MagicMock()

        # Mock paginator
        mock_paginator = MagicMock()
        mock_page = {
            "Contents": [
                {
                    "Key": "file1.txt",
                    "Size": 12,
                    "ETag": '"abc"',
                    "LastModified": MagicMock(timestamp=lambda: 1234567890),
                }
            ]
        }
        mock_paginator.paginate.return_value = [mock_page]
        mock_client.get_paginator.return_value = mock_paginator

        mock_client.get_object.return_value = {
            "Body": mock_body,
            "ContentType": "text/plain",
            "Metadata": {},
            "ETag": '"abc"',
        }
        mock_boto.return_value = mock_client

        manager = DataManager(
            endpoint="localhost:3900",
            access_key="test-key",
            secret_key="test-secret",
        )

        archive_path = tmp_path / "backup.tar.gz"
        manifest = manager.export_bucket("test-bucket", str(archive_path))

        assert archive_path.exists()
        assert manifest.total_objects == 1

        # Verify archive contents
        with tarfile.open(str(archive_path), "r:gz") as tar:
            names = tar.getnames()
            assert "file1.txt" in names
            assert "_manifest.json" in names

    @patch("boto3.client")
    def test_import_bucket_archive(self, mock_boto, tmp_path):
        """Test importing from tar.gz archive to bucket."""
        # Create test archive
        archive_path = tmp_path / "backup.tar.gz"
        with tarfile.open(str(archive_path), "w:gz") as tar:
            # Add a test file
            data = b"test content"
            info = tarfile.TarInfo(name="test.txt")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

            # Add manifest
            manifest = {
                "version": "1.0",
                "bucket": "test-bucket",
                "objects": [
                    {"key": "test.txt", "content_type": "text/plain", "metadata": {}}
                ],
            }
            manifest_data = json.dumps(manifest).encode()
            manifest_info = tarfile.TarInfo(name="_manifest.json")
            manifest_info.size = len(manifest_data)
            tar.addfile(manifest_info, io.BytesIO(manifest_data))

        mock_client = MagicMock()
        mock_client.put_object.return_value = {"ETag": '"abc"'}
        mock_boto.return_value = mock_client

        manager = DataManager(
            endpoint="localhost:3900",
            access_key="test-key",
            secret_key="test-secret",
        )

        result = manager.import_bucket("test-bucket", str(archive_path))

        assert result["imported"] == 1
        mock_client.put_object.assert_called_once()
