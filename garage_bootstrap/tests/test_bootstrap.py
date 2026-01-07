"""
Tests for the bootstrap module.
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
import yaml

from garage_bootstrap.bootstrap import (
    BucketConfig,
    ClusterConfig,
    GarageBootstrap,
    KeyConfig,
    load_config_from_env,
    load_config_from_file,
    parse_config,
)


class TestConfigParsing:
    """Tests for configuration parsing."""

    def test_parse_simple_buckets(self):
        """Test parsing simple bucket names."""
        data = {"buckets": ["bucket1", "bucket2"]}
        config = parse_config(data)

        assert len(config.buckets) == 2
        assert config.buckets[0].name == "bucket1"
        assert config.buckets[1].name == "bucket2"

    def test_parse_bucket_with_options(self):
        """Test parsing bucket with full options."""
        data = {
            "buckets": [
                {
                    "name": "my-bucket",
                    "quotas": {"maxSize": 1024},
                    "keys": ["key1"],
                    "permissions": {"key1": {"read": True, "write": True, "owner": False}},
                }
            ]
        }
        config = parse_config(data)

        assert len(config.buckets) == 1
        bucket = config.buckets[0]
        assert bucket.name == "my-bucket"
        assert bucket.quotas == {"maxSize": 1024}
        assert "key1" in bucket.keys

    def test_parse_simple_keys(self):
        """Test parsing simple key names."""
        data = {"keys": ["key1", "key2"]}
        config = parse_config(data)

        assert len(config.keys) == 2
        assert config.keys[0].name == "key1"

    def test_parse_key_with_options(self):
        """Test parsing key with options."""
        data = {"keys": [{"name": "admin-key", "allowCreateBucket": True}]}
        config = parse_config(data)

        assert len(config.keys) == 1
        assert config.keys[0].name == "admin-key"
        assert config.keys[0].allow_create_bucket is True

    def test_load_config_from_yaml_file(self):
        """Test loading configuration from YAML file."""
        config_data = {
            "buckets": ["test-bucket"],
            "keys": ["test-key"],
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(config_data, f)
            f.flush()

            try:
                config = load_config_from_file(f.name)
                assert len(config.buckets) == 1
                assert config.buckets[0].name == "test-bucket"
            finally:
                os.unlink(f.name)

    def test_load_config_from_json_file(self):
        """Test loading configuration from JSON file."""
        config_data = {
            "buckets": ["test-bucket"],
            "keys": ["test-key"],
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(config_data, f)
            f.flush()

            try:
                config = load_config_from_file(f.name)
                assert len(config.buckets) == 1
            finally:
                os.unlink(f.name)

    def test_load_config_from_env(self, mock_env_vars):
        """Test loading configuration from environment variables."""
        config = load_config_from_env()

        assert len(config.buckets) == 2
        assert len(config.keys) == 2

    def test_load_config_from_env_json(self):
        """Test loading full JSON config from environment."""
        config_json = json.dumps(
            {
                "buckets": [{"name": "env-bucket", "keys": ["env-key"]}],
                "keys": [{"name": "env-key"}],
            }
        )

        with patch.dict(os.environ, {"GARAGE_BOOTSTRAP_CONFIG": config_json}):
            config = load_config_from_env()

        assert len(config.buckets) == 1
        assert config.buckets[0].name == "env-bucket"


class TestGarageBootstrap:
    """Tests for GarageBootstrap class."""

    @patch("garage_bootstrap.admin_client.GarageAdminClient")
    def test_bootstrap_creates_keys(self, mock_client_class):
        """Test that bootstrap creates keys."""
        mock_client = MagicMock()
        mock_client.list_keys.return_value = []
        mock_client.create_key.return_value = {
            "accessKeyId": "GK123",
            "secretAccessKey": "secret123",
            "name": "test-key",
        }

        bootstrap = GarageBootstrap(mock_client)
        config = ClusterConfig(keys=[KeyConfig(name="test-key")])

        result = bootstrap.bootstrap(config, wait_for_ready=False)

        assert len(result["keys"]) == 1
        assert result["keys"][0]["created"] is True
        mock_client.create_key.assert_called_once_with("test-key")

    @patch("garage_bootstrap.admin_client.GarageAdminClient")
    def test_bootstrap_skips_existing_keys(self, mock_client_class):
        """Test that bootstrap skips existing keys."""
        mock_client = MagicMock()
        mock_client.list_keys.return_value = [{"id": "GK123", "name": "existing-key"}]
        mock_client.get_key.return_value = {
            "accessKeyId": "GK123",
            "name": "existing-key",
        }

        bootstrap = GarageBootstrap(mock_client)
        config = ClusterConfig(keys=[KeyConfig(name="existing-key")])

        result = bootstrap.bootstrap(config, wait_for_ready=False)

        assert len(result["keys"]) == 1
        assert result["keys"][0]["created"] is False
        mock_client.create_key.assert_not_called()

    @patch("garage_bootstrap.admin_client.GarageAdminClient")
    def test_bootstrap_creates_buckets(self, mock_client_class):
        """Test that bootstrap creates buckets."""
        mock_client = MagicMock()
        mock_client.list_buckets.return_value = []
        mock_client.create_bucket.return_value = {
            "id": "bucket-123",
            "globalAliases": ["test-bucket"],
        }
        mock_client.find_or_create_bucket.return_value = {
            "id": "bucket-123",
        }

        bootstrap = GarageBootstrap(mock_client)
        config = ClusterConfig(buckets=[BucketConfig(name="test-bucket")])

        result = bootstrap.bootstrap(config, wait_for_ready=False)

        assert len(result["buckets"]) == 1

    @patch("garage_bootstrap.admin_client.GarageAdminClient")
    def test_bootstrap_sets_bucket_permissions(self, mock_client_class):
        """Test that bootstrap sets bucket permissions for keys."""
        mock_client = MagicMock()
        mock_client.list_keys.return_value = []
        mock_client.create_key.return_value = {
            "accessKeyId": "GK123",
            "secretAccessKey": "secret",
            "name": "app-key",
        }
        mock_client.find_or_create_bucket.return_value = {
            "id": "bucket-123",
        }

        bootstrap = GarageBootstrap(mock_client)
        config = ClusterConfig(
            keys=[KeyConfig(name="app-key")],
            buckets=[
                BucketConfig(
                    name="app-bucket",
                    keys=["app-key"],
                    permissions={"app-key": {"read": True, "write": True, "owner": False}},
                )
            ],
        )

        result = bootstrap.bootstrap(config, wait_for_ready=False)

        mock_client.allow_key_on_bucket.assert_called_once()
        call_args = mock_client.allow_key_on_bucket.call_args
        assert call_args[1]["read"] is True
        assert call_args[1]["write"] is True
