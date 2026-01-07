"""
Multi-stage persistence tests for Garage.

These tests verify data persistence between Garage pod restarts,
ensuring that objects survive cluster restarts.
"""

import hashlib
import json
import logging
import os
import tempfile
import time
import uuid
from typing import Dict, List, Optional

import pytest

logger = logging.getLogger(__name__)


class PersistenceTestData:
    """Manages test data for persistence testing across stages."""

    def __init__(self, state_file: str = None):
        """
        Initialize persistence test data manager.

        Args:
            state_file: Path to file for storing test state between stages.
                       If None, uses a user-specific temp directory for security.
        """
        if state_file is None:
            # Use a user-specific temp directory for security in multi-tenant environments
            temp_dir = tempfile.gettempdir()
            user_dir = os.path.join(temp_dir, f"garage_test_{os.getuid()}")
            os.makedirs(user_dir, mode=0o700, exist_ok=True)
            state_file = os.path.join(user_dir, "persistence_test_state.json")
        self.state_file = state_file
        self.state: Dict = {}

    def load_state(self) -> Dict:
        """Load state from file if exists."""
        if os.path.exists(self.state_file):
            with open(self.state_file, "r") as f:
                self.state = json.load(f)
        return self.state

    def save_state(self):
        """Save state to file."""
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2)

    def clear_state(self):
        """Clear state file."""
        if os.path.exists(self.state_file):
            os.unlink(self.state_file)
        self.state = {}


def generate_test_objects(count: int = 10, size_bytes: int = 1024) -> List[Dict]:
    """
    Generate test objects for persistence testing.

    Args:
        count: Number of objects to generate
        size_bytes: Size of each object in bytes

    Returns:
        List of test object metadata
    """
    objects = []
    for i in range(count):
        data = os.urandom(size_bytes)
        obj = {
            "key": f"persistence-test/{uuid.uuid4()}.bin",
            "data": data.hex(),
            "size": size_bytes,
            "checksum": hashlib.sha256(data).hexdigest(),
        }
        objects.append(obj)
    return objects


class TestPersistenceStage1:
    """Stage 1: Create test data before pod restart."""

    @pytest.fixture
    def s3_client(self, s3_test_config):
        """Create S3 client for testing."""
        import boto3
        from botocore.config import Config

        endpoint = s3_test_config["endpoint"]
        if not endpoint.startswith(("http://", "https://")):
            endpoint = f"http://{endpoint}"

        return boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=s3_test_config["access_key"],
            aws_secret_access_key=s3_test_config["secret_key"],
            region_name=s3_test_config["region"],
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    @pytest.fixture
    def test_state(self):
        """Get test state manager."""
        state = PersistenceTestData()
        state.clear_state()  # Start fresh for stage 1
        return state

    @pytest.mark.persistence
    @pytest.mark.stage1
    def test_create_objects(self, s3_client, s3_test_config, test_state):
        """Create test objects and record their metadata."""
        bucket = s3_test_config["bucket"]

        # Ensure bucket exists
        try:
            s3_client.head_bucket(Bucket=bucket)
        except Exception:
            pytest.skip(f"Bucket {bucket} does not exist - skipping persistence test")

        # Generate and upload test objects
        test_objects = generate_test_objects(count=5, size_bytes=512)

        uploaded = []
        for obj in test_objects:
            data = bytes.fromhex(obj["data"])
            s3_client.put_object(
                Bucket=bucket,
                Key=obj["key"],
                Body=data,
            )
            uploaded.append({
                "key": obj["key"],
                "checksum": obj["checksum"],
                "size": obj["size"],
            })
            logger.info(f"Uploaded: {obj['key']}")

        # Save state for stage 2
        test_state.state = {
            "bucket": bucket,
            "objects": uploaded,
            "stage1_completed": True,
            "timestamp": time.time(),
        }
        test_state.save_state()

        assert len(uploaded) == 5
        logger.info("Stage 1 complete: Created 5 test objects")

    @pytest.mark.persistence
    @pytest.mark.stage1
    def test_verify_objects_exist(self, s3_client, s3_test_config, test_state):
        """Verify objects exist after creation."""
        test_state.load_state()

        if not test_state.state.get("stage1_completed"):
            pytest.skip("Stage 1 creation not completed")

        bucket = test_state.state["bucket"]

        for obj in test_state.state["objects"]:
            response = s3_client.get_object(Bucket=bucket, Key=obj["key"])
            data = response["Body"].read()
            checksum = hashlib.sha256(data).hexdigest()

            assert checksum == obj["checksum"], f"Checksum mismatch for {obj['key']}"
            assert len(data) == obj["size"], f"Size mismatch for {obj['key']}"

        logger.info("Stage 1 verification complete: All objects verified")


class TestPersistenceStage2:
    """Stage 2: Verify data after pod restart."""

    @pytest.fixture
    def s3_client(self, s3_test_config):
        """Create S3 client for testing."""
        import boto3
        from botocore.config import Config

        endpoint = s3_test_config["endpoint"]
        if not endpoint.startswith(("http://", "https://")):
            endpoint = f"http://{endpoint}"

        return boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=s3_test_config["access_key"],
            aws_secret_access_key=s3_test_config["secret_key"],
            region_name=s3_test_config["region"],
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    @pytest.fixture
    def test_state(self):
        """Get test state manager with existing state."""
        state = PersistenceTestData()
        state.load_state()
        return state

    @pytest.mark.persistence
    @pytest.mark.stage2
    def test_objects_persist_after_restart(self, s3_client, test_state):
        """Verify all objects still exist after pod restart."""
        if not test_state.state.get("stage1_completed"):
            pytest.skip("Stage 1 not completed - run stage 1 first")

        bucket = test_state.state["bucket"]
        objects = test_state.state["objects"]

        verified = 0
        for obj in objects:
            try:
                response = s3_client.get_object(Bucket=bucket, Key=obj["key"])
                data = response["Body"].read()
                checksum = hashlib.sha256(data).hexdigest()

                assert checksum == obj["checksum"], f"Checksum mismatch for {obj['key']}"
                assert len(data) == obj["size"], f"Size mismatch for {obj['key']}"
                verified += 1
                logger.info(f"Verified: {obj['key']}")

            except Exception as e:
                pytest.fail(f"Object {obj['key']} not found after restart: {e}")

        assert verified == len(objects)
        logger.info(f"Stage 2 complete: All {verified} objects verified after restart")

    @pytest.mark.persistence
    @pytest.mark.stage2
    def test_data_integrity(self, s3_client, test_state):
        """Verify data integrity after restart."""
        if not test_state.state.get("stage1_completed"):
            pytest.skip("Stage 1 not completed - run stage 1 first")

        bucket = test_state.state["bucket"]

        # List all objects with persistence-test prefix
        response = s3_client.list_objects_v2(Bucket=bucket, Prefix="persistence-test/")

        if "Contents" not in response:
            pytest.skip("No persistence test objects found")

        expected_keys = {obj["key"] for obj in test_state.state["objects"]}
        actual_keys = {obj["Key"] for obj in response.get("Contents", [])}

        # All expected keys should be present
        missing = expected_keys - actual_keys
        assert not missing, f"Missing objects after restart: {missing}"

        logger.info("Data integrity verified after restart")

    @pytest.mark.persistence
    @pytest.mark.stage2
    def test_cleanup(self, s3_client, test_state):
        """Clean up test objects after verification."""
        if not test_state.state.get("stage1_completed"):
            pytest.skip("Stage 1 not completed")

        bucket = test_state.state["bucket"]

        for obj in test_state.state["objects"]:
            try:
                s3_client.delete_object(Bucket=bucket, Key=obj["key"])
                logger.info(f"Deleted: {obj['key']}")
            except Exception as e:
                logger.warning(f"Failed to delete {obj['key']}: {e}")

        # Clear state
        test_state.clear_state()
        logger.info("Cleanup complete")


def run_persistence_test_stage1(
    endpoint: str,
    access_key: str,
    secret_key: str,
    bucket: str,
    region: str = "garage",
) -> Dict:
    """
    Run stage 1 of persistence test programmatically.

    Args:
        endpoint: S3 endpoint
        access_key: Access key ID
        secret_key: Secret access key
        bucket: Bucket name
        region: Region name

    Returns:
        Dictionary with test results
    """
    import boto3
    from botocore.config import Config

    if not endpoint.startswith(("http://", "https://")):
        endpoint = f"http://{endpoint}"

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )

    state = PersistenceTestData()
    state.clear_state()

    test_objects = generate_test_objects(count=5, size_bytes=512)
    uploaded = []

    for obj in test_objects:
        data = bytes.fromhex(obj["data"])
        client.put_object(Bucket=bucket, Key=obj["key"], Body=data)
        uploaded.append({
            "key": obj["key"],
            "checksum": obj["checksum"],
            "size": obj["size"],
        })

    state.state = {
        "bucket": bucket,
        "objects": uploaded,
        "stage1_completed": True,
        "timestamp": time.time(),
    }
    state.save_state()

    return {"success": True, "objects_created": len(uploaded)}


def run_persistence_test_stage2(
    endpoint: str,
    access_key: str,
    secret_key: str,
    region: str = "garage",
    cleanup: bool = True,
) -> Dict:
    """
    Run stage 2 of persistence test programmatically.

    Args:
        endpoint: S3 endpoint
        access_key: Access key ID
        secret_key: Secret access key
        region: Region name
        cleanup: Whether to delete test objects after verification

    Returns:
        Dictionary with test results
    """
    import boto3
    from botocore.config import Config

    if not endpoint.startswith(("http://", "https://")):
        endpoint = f"http://{endpoint}"

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )

    state = PersistenceTestData()
    state.load_state()

    if not state.state.get("stage1_completed"):
        return {"success": False, "error": "Stage 1 not completed"}

    bucket = state.state["bucket"]
    results = {"verified": 0, "failed": 0, "errors": []}

    for obj in state.state["objects"]:
        try:
            response = client.get_object(Bucket=bucket, Key=obj["key"])
            data = response["Body"].read()
            checksum = hashlib.sha256(data).hexdigest()

            if checksum != obj["checksum"]:
                results["failed"] += 1
                results["errors"].append(f"Checksum mismatch: {obj['key']}")
            elif len(data) != obj["size"]:
                results["failed"] += 1
                results["errors"].append(f"Size mismatch: {obj['key']}")
            else:
                results["verified"] += 1
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"Not found: {obj['key']}: {e}")

    results["success"] = results["failed"] == 0

    if cleanup and results["success"]:
        for obj in state.state["objects"]:
            try:
                client.delete_object(Bucket=bucket, Key=obj["key"])
            except Exception:
                pass
        state.clear_state()

    return results
