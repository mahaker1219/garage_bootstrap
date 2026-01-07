"""
Tests for connectivity module.

These tests verify that the connectivity test classes work correctly
with mocked S3 clients.
"""

import io
from unittest.mock import MagicMock, patch

import pytest

from garage_test.connectivity import (
    MinioConnectivityTest,
    S3ConnectivityTest,
    AzureBlobConnectivityTest,
    run_all_connectivity_tests,
)


class TestMinioConnectivity:
    """Tests for MinIO connectivity testing."""

    @patch("minio.Minio")
    def test_connect(self, mock_minio):
        """Test MinIO connection."""
        test = MinioConnectivityTest(
            endpoint="localhost:3900",
            access_key="test-key",
            secret_key="test-secret",
            bucket="test-bucket",
        )

        result = test.connect()

        assert result is True
        mock_minio.assert_called_once()

    @patch("minio.Minio")
    def test_bucket_exists(self, mock_minio):
        """Test bucket existence check."""
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_minio.return_value = mock_client

        test = MinioConnectivityTest(
            endpoint="localhost:3900",
            access_key="test-key",
            secret_key="test-secret",
            bucket="test-bucket",
        )
        test.connect()

        result = test.test_bucket_exists()

        assert result is True
        mock_client.bucket_exists.assert_called_with("test-bucket")

    @patch("minio.Minio")
    def test_put_object(self, mock_minio):
        """Test putting an object."""
        mock_client = MagicMock()
        mock_minio.return_value = mock_client

        test = MinioConnectivityTest(
            endpoint="localhost:3900",
            access_key="test-key",
            secret_key="test-secret",
            bucket="test-bucket",
        )
        test.connect()

        result = test.test_put_object("test-key", b"test-data")

        assert result is True
        mock_client.put_object.assert_called_once()

    @patch("minio.Minio")
    def test_get_object(self, mock_minio):
        """Test getting an object."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"test-data"

        mock_client = MagicMock()
        mock_client.get_object.return_value = mock_response
        mock_minio.return_value = mock_client

        test = MinioConnectivityTest(
            endpoint="localhost:3900",
            access_key="test-key",
            secret_key="test-secret",
            bucket="test-bucket",
        )
        test.connect()

        result = test.test_get_object("test-key")

        assert result == b"test-data"

    @patch("minio.Minio")
    def test_full_test_suite(self, mock_minio):
        """Test running the full test suite."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"Hello from Garage Bootstrap connectivity test!"

        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_client.get_object.return_value = mock_response
        mock_client.list_objects.return_value = []
        mock_minio.return_value = mock_client

        test = MinioConnectivityTest(
            endpoint="localhost:3900",
            access_key="test-key",
            secret_key="test-secret",
            bucket="test-bucket",
        )

        result = test.run_full_test()

        assert result["success"] is True
        assert result["tests"]["connect"] is True
        assert result["tests"]["bucket_exists"] is True


class TestS3Connectivity:
    """Tests for boto3 S3 connectivity testing."""

    @patch("boto3.client")
    def test_connect(self, mock_boto_client):
        """Test S3 connection."""
        test = S3ConnectivityTest(
            endpoint="http://localhost:3900",
            access_key="test-key",
            secret_key="test-secret",
            bucket="test-bucket",
        )

        result = test.connect()

        assert result is True
        mock_boto_client.assert_called_once()

    @patch("boto3.client")
    def test_bucket_exists(self, mock_boto_client):
        """Test bucket existence check."""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        test = S3ConnectivityTest(
            endpoint="http://localhost:3900",
            access_key="test-key",
            secret_key="test-secret",
            bucket="test-bucket",
        )
        test.connect()

        result = test.test_bucket_exists()

        assert result is True
        mock_client.head_bucket.assert_called_with(Bucket="test-bucket")

    @patch("boto3.client")
    def test_put_object(self, mock_boto_client):
        """Test putting an object."""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        test = S3ConnectivityTest(
            endpoint="http://localhost:3900",
            access_key="test-key",
            secret_key="test-secret",
            bucket="test-bucket",
        )
        test.connect()

        result = test.test_put_object("test-key", b"test-data")

        assert result is True
        mock_client.put_object.assert_called_once()

    @patch("boto3.client")
    def test_get_object(self, mock_boto_client):
        """Test getting an object."""
        mock_body = MagicMock()
        mock_body.read.return_value = b"test-data"

        mock_client = MagicMock()
        mock_client.get_object.return_value = {"Body": mock_body}
        mock_boto_client.return_value = mock_client

        test = S3ConnectivityTest(
            endpoint="http://localhost:3900",
            access_key="test-key",
            secret_key="test-secret",
            bucket="test-bucket",
        )
        test.connect()

        result = test.test_get_object("test-key")

        assert result == b"test-data"

    @patch("boto3.client")
    def test_list_objects(self, mock_boto_client):
        """Test listing objects."""
        mock_client = MagicMock()
        mock_client.list_objects_v2.return_value = {
            "Contents": [{"Key": "obj1"}, {"Key": "obj2"}]
        }
        mock_boto_client.return_value = mock_client

        test = S3ConnectivityTest(
            endpoint="http://localhost:3900",
            access_key="test-key",
            secret_key="test-secret",
            bucket="test-bucket",
        )
        test.connect()

        result = test.test_list_objects()

        assert result == ["obj1", "obj2"]


class TestAzureBlobConnectivity:
    """Tests for Azure Blob connectivity testing."""

    @patch("azure.storage.blob.BlobServiceClient")
    def test_connect(self, mock_blob_client):
        """Test Azure Blob connection."""
        mock_service = MagicMock()
        mock_blob_client.from_connection_string.return_value = mock_service

        test = AzureBlobConnectivityTest(
            endpoint="http://localhost:3900",
            access_key="test-key",
            secret_key="test-secret",
            bucket="test-bucket",
        )

        result = test.connect()

        assert result is True

    @patch("azure.storage.blob.BlobServiceClient")
    def test_put_object(self, mock_blob_client):
        """Test putting a blob."""
        mock_service = MagicMock()
        mock_container = MagicMock()
        mock_blob = MagicMock()

        mock_service.get_container_client.return_value = mock_container
        mock_container.get_blob_client.return_value = mock_blob
        mock_blob_client.from_connection_string.return_value = mock_service

        test = AzureBlobConnectivityTest(
            endpoint="http://localhost:3900",
            access_key="test-key",
            secret_key="test-secret",
            bucket="test-bucket",
        )
        test.connect()

        result = test.test_put_object("test-key", b"test-data")

        assert result is True
        mock_blob.upload_blob.assert_called_once()


class TestRunAllConnectivityTests:
    """Tests for running all connectivity tests."""

    @patch("garage_test.connectivity.MinioConnectivityTest")
    @patch("garage_test.connectivity.S3ConnectivityTest")
    @patch("garage_test.connectivity.AzureBlobConnectivityTest")
    def test_all_pass(self, mock_azure, mock_s3, mock_minio):
        """Test that all libraries pass connectivity tests."""
        for mock_class in [mock_minio, mock_s3, mock_azure]:
            mock_instance = MagicMock()
            mock_instance.run_full_test.return_value = {"success": True, "tests": {}}
            mock_class.return_value = mock_instance

        results = run_all_connectivity_tests(
            endpoint="localhost:3900",
            access_key="test-key",
            secret_key="test-secret",
            bucket="test-bucket",
        )

        assert results["overall_success"] is True
        assert "minio" in results["libraries"]
        assert "s3" in results["libraries"]
        assert "azure" in results["libraries"]

    @patch("garage_test.connectivity.MinioConnectivityTest")
    @patch("garage_test.connectivity.S3ConnectivityTest")
    @patch("garage_test.connectivity.AzureBlobConnectivityTest")
    def test_one_fails(self, mock_azure, mock_s3, mock_minio):
        """Test that overall fails if one library fails."""
        mock_minio_instance = MagicMock()
        mock_minio_instance.run_full_test.return_value = {"success": True, "tests": {}}
        mock_minio.return_value = mock_minio_instance

        mock_s3_instance = MagicMock()
        mock_s3_instance.run_full_test.return_value = {"success": False, "tests": {}}
        mock_s3.return_value = mock_s3_instance

        mock_azure_instance = MagicMock()
        mock_azure_instance.run_full_test.return_value = {"success": True, "tests": {}}
        mock_azure.return_value = mock_azure_instance

        results = run_all_connectivity_tests(
            endpoint="localhost:3900",
            access_key="test-key",
            secret_key="test-secret",
            bucket="test-bucket",
        )

        assert results["overall_success"] is False
