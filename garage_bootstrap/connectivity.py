"""
Connectivity testing module for Garage S3 storage.

Provides test utilities for verifying S3-compatible storage connectivity
using multiple client libraries: MinIO, boto3 (S3), and Azure Blob Storage.
"""

import io
import logging
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class BaseConnectivityTest(ABC):
    """Base class for connectivity tests."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "garage",
        secure: bool = False,
    ):
        """
        Initialize connectivity test.

        Args:
            endpoint: S3 endpoint URL
            access_key: Access key ID
            secret_key: Secret access key
            bucket: Bucket name to test with
            region: Region name (default: garage)
            secure: Use HTTPS (default: False for local testing)
        """
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket = bucket
        self.region = region
        self.secure = secure
        self.client = None

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to the storage service."""
        pass

    @abstractmethod
    def test_bucket_exists(self) -> bool:
        """Test if the configured bucket exists."""
        pass

    @abstractmethod
    def test_put_object(self, key: str, data: bytes) -> bool:
        """Test putting an object into the bucket."""
        pass

    @abstractmethod
    def test_get_object(self, key: str) -> Optional[bytes]:
        """Test getting an object from the bucket."""
        pass

    @abstractmethod
    def test_delete_object(self, key: str) -> bool:
        """Test deleting an object from the bucket."""
        pass

    @abstractmethod
    def test_list_objects(self, prefix: str = "") -> list:
        """Test listing objects in the bucket."""
        pass

    def run_full_test(self) -> Dict[str, Any]:
        """
        Run a full connectivity test suite.

        Returns:
            Dictionary with test results
        """
        results = {
            "library": self.__class__.__name__,
            "endpoint": self.endpoint,
            "bucket": self.bucket,
            "tests": {},
            "success": True,
        }

        test_key = f"connectivity-test-{uuid.uuid4()}.txt"
        test_data = b"Hello from Garage Bootstrap connectivity test!"

        # Test connection
        try:
            results["tests"]["connect"] = self.connect()
        except Exception as e:
            results["tests"]["connect"] = False
            results["tests"]["connect_error"] = str(e)
            results["success"] = False
            return results

        # Test bucket exists
        try:
            results["tests"]["bucket_exists"] = self.test_bucket_exists()
        except Exception as e:
            results["tests"]["bucket_exists"] = False
            results["tests"]["bucket_exists_error"] = str(e)

        # Test put object
        try:
            results["tests"]["put_object"] = self.test_put_object(test_key, test_data)
        except Exception as e:
            results["tests"]["put_object"] = False
            results["tests"]["put_object_error"] = str(e)

        # Test get object
        try:
            retrieved_data = self.test_get_object(test_key)
            results["tests"]["get_object"] = retrieved_data == test_data
        except Exception as e:
            results["tests"]["get_object"] = False
            results["tests"]["get_object_error"] = str(e)

        # Test list objects
        try:
            objects = self.test_list_objects()
            results["tests"]["list_objects"] = isinstance(objects, list)
        except Exception as e:
            results["tests"]["list_objects"] = False
            results["tests"]["list_objects_error"] = str(e)

        # Test delete object
        try:
            results["tests"]["delete_object"] = self.test_delete_object(test_key)
        except Exception as e:
            results["tests"]["delete_object"] = False
            results["tests"]["delete_object_error"] = str(e)

        # Check overall success
        results["success"] = all(
            v for k, v in results["tests"].items() if not k.endswith("_error")
        )

        return results


class MinioConnectivityTest(BaseConnectivityTest):
    """Connectivity test using the MinIO Python client."""

    def connect(self) -> bool:
        """Establish connection using MinIO client."""
        from minio import Minio

        # Parse endpoint to remove protocol
        endpoint = self.endpoint
        if endpoint.startswith("http://"):
            endpoint = endpoint[7:]
        elif endpoint.startswith("https://"):
            endpoint = endpoint[8:]

        self.client = Minio(
            endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure,
            region=self.region,
        )
        logger.info(f"MinIO client connected to {endpoint}")
        return True

    def test_bucket_exists(self) -> bool:
        """Test if bucket exists using MinIO client."""
        return self.client.bucket_exists(self.bucket)

    def test_put_object(self, key: str, data: bytes) -> bool:
        """Put object using MinIO client."""
        self.client.put_object(
            self.bucket,
            key,
            io.BytesIO(data),
            length=len(data),
            content_type="text/plain",
        )
        return True

    def test_get_object(self, key: str) -> Optional[bytes]:
        """Get object using MinIO client."""
        response = self.client.get_object(self.bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def test_delete_object(self, key: str) -> bool:
        """Delete object using MinIO client."""
        self.client.remove_object(self.bucket, key)
        return True

    def test_list_objects(self, prefix: str = "") -> list:
        """List objects using MinIO client."""
        objects = self.client.list_objects(self.bucket, prefix=prefix)
        return [obj.object_name for obj in objects]


class S3ConnectivityTest(BaseConnectivityTest):
    """Connectivity test using boto3 S3 client."""

    def connect(self) -> bool:
        """Establish connection using boto3."""
        import boto3
        from botocore.config import Config

        # Ensure endpoint has protocol
        endpoint = self.endpoint
        if not endpoint.startswith(("http://", "https://")):
            protocol = "https" if self.secure else "http"
            endpoint = f"{protocol}://{endpoint}"

        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        )
        logger.info(f"boto3 S3 client connected to {endpoint}")
        return True

    def test_bucket_exists(self) -> bool:
        """Test if bucket exists using boto3."""
        try:
            self.client.head_bucket(Bucket=self.bucket)
            return True
        except Exception:
            return False

    def test_put_object(self, key: str, data: bytes) -> bool:
        """Put object using boto3."""
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType="text/plain",
        )
        return True

    def test_get_object(self, key: str) -> Optional[bytes]:
        """Get object using boto3."""
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

    def test_delete_object(self, key: str) -> bool:
        """Delete object using boto3."""
        self.client.delete_object(Bucket=self.bucket, Key=key)
        return True

    def test_list_objects(self, prefix: str = "") -> list:
        """List objects using boto3."""
        response = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
        return [obj["Key"] for obj in response.get("Contents", [])]


class AzureBlobConnectivityTest(BaseConnectivityTest):
    """
    Connectivity test using Azure Blob Storage client.
    
    Note: Garage supports Azure Blob Storage API compatibility.
    This uses the azure-storage-blob library with custom endpoint.
    """

    def connect(self) -> bool:
        """Establish connection using Azure Blob Storage client."""
        from azure.storage.blob import BlobServiceClient

        # Build connection string for S3-compatible endpoint
        # Azure SDK can work with S3-compatible endpoints using custom settings
        endpoint = self.endpoint
        if not endpoint.startswith(("http://", "https://")):
            protocol = "https" if self.secure else "http"
            endpoint = f"{protocol}://{endpoint}"

        # Create a custom account URL for the blob service
        # For S3-compatible storage, we use a custom approach
        self.endpoint_url = endpoint
        
        # Azure Blob Storage client with custom endpoint
        # Note: This requires proper S3-to-Azure compatibility layer or
        # the endpoint must support Azure Blob API
        connection_string = (
            f"DefaultEndpointsProtocol={'https' if self.secure else 'http'};"
            f"AccountName={self.access_key};"
            f"AccountKey={self.secret_key};"
            f"BlobEndpoint={endpoint};"
        )
        
        try:
            self.client = BlobServiceClient.from_connection_string(connection_string)
            self.container_client = self.client.get_container_client(self.bucket)
            logger.info(f"Azure Blob client connected to {endpoint}")
            return True
        except Exception as e:
            logger.warning(f"Azure Blob connection failed: {e}")
            # Fall back to using account URL directly
            self.client = BlobServiceClient(
                account_url=endpoint,
                credential={"account_name": self.access_key, "account_key": self.secret_key},
            )
            self.container_client = self.client.get_container_client(self.bucket)
            return True

    def test_bucket_exists(self) -> bool:
        """Test if container exists using Azure client."""
        try:
            self.container_client.get_container_properties()
            return True
        except Exception:
            return False

    def test_put_object(self, key: str, data: bytes) -> bool:
        """Put blob using Azure client."""
        blob_client = self.container_client.get_blob_client(key)
        blob_client.upload_blob(data, overwrite=True)
        return True

    def test_get_object(self, key: str) -> Optional[bytes]:
        """Get blob using Azure client."""
        blob_client = self.container_client.get_blob_client(key)
        return blob_client.download_blob().readall()

    def test_delete_object(self, key: str) -> bool:
        """Delete blob using Azure client."""
        blob_client = self.container_client.get_blob_client(key)
        blob_client.delete_blob()
        return True

    def test_list_objects(self, prefix: str = "") -> list:
        """List blobs using Azure client."""
        blobs = self.container_client.list_blobs(name_starts_with=prefix)
        return [blob.name for blob in blobs]


def run_all_connectivity_tests(
    endpoint: str,
    access_key: str,
    secret_key: str,
    bucket: str,
    region: str = "garage",
    secure: bool = False,
) -> Dict[str, Any]:
    """
    Run connectivity tests with all supported libraries.

    Args:
        endpoint: S3 endpoint URL
        access_key: Access key ID
        secret_key: Secret access key
        bucket: Bucket name to test
        region: Region name
        secure: Use HTTPS

    Returns:
        Dictionary with test results for all libraries
    """
    results = {"overall_success": True, "libraries": {}}

    test_classes = [
        ("minio", MinioConnectivityTest),
        ("s3", S3ConnectivityTest),
        ("azure", AzureBlobConnectivityTest),
    ]

    for name, test_class in test_classes:
        try:
            test = test_class(
                endpoint=endpoint,
                access_key=access_key,
                secret_key=secret_key,
                bucket=bucket,
                region=region,
                secure=secure,
            )
            result = test.run_full_test()
            results["libraries"][name] = result
            if not result["success"]:
                results["overall_success"] = False
        except ImportError as e:
            results["libraries"][name] = {
                "success": False,
                "error": f"Library not installed: {e}",
            }
            results["overall_success"] = False
        except Exception as e:
            results["libraries"][name] = {
                "success": False,
                "error": str(e),
            }
            results["overall_success"] = False

    return results
