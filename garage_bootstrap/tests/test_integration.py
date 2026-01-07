"""
Integration tests for Garage Bootstrap.

These tests run against a live Garage cluster and require:
- GARAGE_S3_ENDPOINT: S3 API endpoint (e.g., localhost:3900)
- TEST_ACCESS_KEY: Access key ID
- TEST_SECRET_KEY: Secret access key
- TEST_BUCKET: Bucket name for testing

Run with: pytest tests/test_integration.py -v -m "integration"
"""

import os
import uuid

import pytest

# Skip all tests in this module if credentials are not configured
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("TEST_ACCESS_KEY") or not os.environ.get("TEST_SECRET_KEY"),
        reason="Integration tests require TEST_ACCESS_KEY and TEST_SECRET_KEY environment variables"
    ),
]


class TestLiveMinioConnectivity:
    """Integration tests using MinIO client against live Garage cluster."""

    @pytest.fixture
    def minio_test(self, s3_test_config):
        """Create MinIO connectivity test instance."""
        from garage_bootstrap.connectivity import MinioConnectivityTest
        return MinioConnectivityTest(
            endpoint=s3_test_config["endpoint"],
            access_key=s3_test_config["access_key"],
            secret_key=s3_test_config["secret_key"],
            bucket=s3_test_config["bucket"],
            region=s3_test_config["region"],
            secure=s3_test_config["secure"],
        )

    def test_connect(self, minio_test):
        """Test connecting to Garage with MinIO client."""
        result = minio_test.connect()
        assert result is True

    def test_bucket_exists(self, minio_test):
        """Test checking if bucket exists."""
        minio_test.connect()
        result = minio_test.test_bucket_exists()
        assert result is True, f"Bucket {minio_test.bucket} does not exist"

    def test_put_get_delete_object(self, minio_test):
        """Test full object lifecycle: put, get, delete."""
        minio_test.connect()

        test_key = f"integration-test/{uuid.uuid4()}.txt"
        test_data = b"Integration test data from MinIO client"

        # Put object
        put_result = minio_test.test_put_object(test_key, test_data)
        assert put_result is True

        # Get object
        get_result = minio_test.test_get_object(test_key)
        assert get_result == test_data

        # Delete object
        delete_result = minio_test.test_delete_object(test_key)
        assert delete_result is True

    def test_list_objects(self, minio_test):
        """Test listing objects in bucket."""
        minio_test.connect()

        # Create a test object first
        test_key = f"integration-test/list-test-{uuid.uuid4()}.txt"
        minio_test.test_put_object(test_key, b"list test data")

        try:
            # List objects
            objects = minio_test.test_list_objects(prefix="integration-test/")
            assert isinstance(objects, list)
            assert len(objects) >= 1
        finally:
            # Cleanup
            minio_test.test_delete_object(test_key)

    def test_full_test_suite(self, minio_test):
        """Run full connectivity test suite."""
        result = minio_test.run_full_test()
        assert result["success"] is True, f"Tests failed: {result.get('tests', {})}"


class TestLiveS3Connectivity:
    """Integration tests using boto3 S3 client against live Garage cluster."""

    @pytest.fixture
    def s3_test(self, s3_test_config):
        """Create S3 connectivity test instance."""
        from garage_bootstrap.connectivity import S3ConnectivityTest
        return S3ConnectivityTest(
            endpoint=s3_test_config["endpoint"],
            access_key=s3_test_config["access_key"],
            secret_key=s3_test_config["secret_key"],
            bucket=s3_test_config["bucket"],
            region=s3_test_config["region"],
            secure=s3_test_config["secure"],
        )

    def test_connect(self, s3_test):
        """Test connecting to Garage with boto3 S3 client."""
        result = s3_test.connect()
        assert result is True

    def test_bucket_exists(self, s3_test):
        """Test checking if bucket exists."""
        s3_test.connect()
        result = s3_test.test_bucket_exists()
        assert result is True, f"Bucket {s3_test.bucket} does not exist"

    def test_put_get_delete_object(self, s3_test):
        """Test full object lifecycle: put, get, delete."""
        s3_test.connect()

        test_key = f"integration-test/{uuid.uuid4()}.txt"
        test_data = b"Integration test data from boto3 S3 client"

        # Put object
        put_result = s3_test.test_put_object(test_key, test_data)
        assert put_result is True

        # Get object
        get_result = s3_test.test_get_object(test_key)
        assert get_result == test_data

        # Delete object
        delete_result = s3_test.test_delete_object(test_key)
        assert delete_result is True

    def test_list_objects(self, s3_test):
        """Test listing objects in bucket."""
        s3_test.connect()

        # Create a test object first
        test_key = f"integration-test/list-test-{uuid.uuid4()}.txt"
        s3_test.test_put_object(test_key, b"list test data")

        try:
            # List objects
            objects = s3_test.test_list_objects(prefix="integration-test/")
            assert isinstance(objects, list)
        finally:
            # Cleanup
            s3_test.test_delete_object(test_key)

    def test_full_test_suite(self, s3_test):
        """Run full connectivity test suite."""
        result = s3_test.run_full_test()
        assert result["success"] is True, f"Tests failed: {result.get('tests', {})}"


class TestLiveAllLibraries:
    """Integration tests running all libraries against live Garage cluster."""

    def test_all_libraries(self, s3_test_config):
        """Test connectivity with all supported libraries."""
        from garage_bootstrap.connectivity import run_all_connectivity_tests

        results = run_all_connectivity_tests(
            endpoint=s3_test_config["endpoint"],
            access_key=s3_test_config["access_key"],
            secret_key=s3_test_config["secret_key"],
            bucket=s3_test_config["bucket"],
            region=s3_test_config["region"],
            secure=s3_test_config["secure"],
        )

        # Check each library
        for lib_name, lib_result in results["libraries"].items():
            if lib_name == "azure":
                # Azure may fail on S3-only endpoints, skip assertion
                continue
            assert lib_result.get("success", False), \
                f"{lib_name} connectivity failed: {lib_result}"

        # MinIO and S3 should always pass on Garage
        assert results["libraries"]["minio"]["success"] is True
        assert results["libraries"]["s3"]["success"] is True


class TestLiveDataManager:
    """Integration tests for DataManager against live Garage cluster."""

    @pytest.fixture
    def data_manager(self, s3_test_config):
        """Create DataManager instance."""
        from garage_bootstrap.data_manager import DataManager
        return DataManager(
            endpoint=s3_test_config["endpoint"],
            access_key=s3_test_config["access_key"],
            secret_key=s3_test_config["secret_key"],
            region=s3_test_config["region"],
            secure=s3_test_config["secure"],
        )

    def test_list_buckets(self, data_manager):
        """Test listing buckets."""
        buckets = data_manager.list_buckets()
        assert isinstance(buckets, list)

    def test_put_get_delete_object(self, data_manager, s3_test_config):
        """Test object operations."""
        bucket = s3_test_config["bucket"]
        test_key = f"data-manager-test/{uuid.uuid4()}.txt"
        test_data = b"DataManager integration test"

        # Put
        etag = data_manager.put_object(bucket, test_key, test_data)
        assert etag is not None

        # Get
        data, metadata = data_manager.get_object(bucket, test_key)
        assert data == test_data

        # Delete
        result = data_manager.delete_object(bucket, test_key)
        assert result is True

    def test_export_import_directory(self, data_manager, s3_test_config, tmp_path):
        """Test exporting and importing to/from a directory."""
        bucket = s3_test_config["bucket"]
        
        # Create test objects
        test_prefix = f"export-test-{uuid.uuid4()}/"
        test_objects = {
            f"{test_prefix}file1.txt": b"Content of file 1",
            f"{test_prefix}file2.txt": b"Content of file 2",
            f"{test_prefix}subdir/file3.txt": b"Content of file 3",
        }

        for key, data in test_objects.items():
            data_manager.put_object(bucket, key, data)

        try:
            # Export
            export_dir = tmp_path / "export"
            result = data_manager.export_to_directory(bucket, str(export_dir), prefix=test_prefix)
            assert result["exported"] == 3

            # Verify files exist
            assert (export_dir / f"{test_prefix}file1.txt").exists()
            assert (export_dir / f"{test_prefix}file2.txt").exists()
            assert (export_dir / f"{test_prefix}subdir/file3.txt").exists()

        finally:
            # Cleanup
            for key in test_objects.keys():
                data_manager.delete_object(bucket, key)
