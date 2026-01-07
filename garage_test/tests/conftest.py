"""
Pytest fixtures for Garage Bootstrap tests.
"""

import os
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_env_vars():
    """Set up mock environment variables for testing."""
    env_vars = {
        "GARAGE_ADMIN_ENDPOINT": "http://localhost:3903",
        "GARAGE_ADMIN_TOKEN": "test-admin-token",
        "GARAGE_S3_ENDPOINT": "http://localhost:3900",
        "GARAGE_BUCKETS": "test-bucket-1,test-bucket-2",
        "GARAGE_KEYS": "test-key-1,test-key-2",
    }
    with patch.dict(os.environ, env_vars):
        yield env_vars


@pytest.fixture
def s3_test_config():
    """Configuration for S3 connectivity tests."""
    return {
        "endpoint": os.environ.get("GARAGE_S3_ENDPOINT", "localhost:3900"),
        "access_key": os.environ.get("TEST_ACCESS_KEY", "GKtest123"),
        "secret_key": os.environ.get("TEST_SECRET_KEY", "testsecret123"),
        "bucket": os.environ.get("TEST_BUCKET", "test-bucket"),
        "region": os.environ.get("TEST_REGION", "garage"),
        "secure": os.environ.get("TEST_SECURE", "false").lower() == "true",
    }


@pytest.fixture
def mock_requests():
    """Mock requests for admin API testing."""
    with patch("requests.Session") as mock_session:
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.content = b"{}"
        mock_session.return_value.request.return_value = mock_response
        yield mock_session


@pytest.fixture
def sample_config():
    """Sample cluster configuration for testing."""
    return {
        "buckets": [
            {
                "name": "app-data",
                "keys": ["app-key"],
                "permissions": {"app-key": {"read": True, "write": True, "owner": False}},
            },
            {
                "name": "backups",
                "quotas": {"maxSize": 10737418240},  # 10GB
            },
        ],
        "keys": [
            {"name": "app-key", "allowCreateBucket": False},
            {"name": "admin-key", "allowCreateBucket": True},
        ],
    }


@pytest.fixture
def temp_backup_dir(tmp_path):
    """Create a temporary directory for backup tests."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    return backup_dir
