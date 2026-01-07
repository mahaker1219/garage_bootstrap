"""
Tests for the admin client module.
"""

import pytest
from unittest.mock import MagicMock, patch

from garage_bootstrap.admin_client import GarageAdminClient


class TestGarageAdminClient:
    """Tests for GarageAdminClient class."""

    def test_init(self):
        """Test client initialization."""
        client = GarageAdminClient(
            admin_endpoint="http://localhost:3903",
            admin_token="test-token",
        )
        assert client.admin_endpoint == "http://localhost:3903"
        assert client.admin_token == "test-token"
        assert "Authorization" in client.session.headers

    def test_endpoint_trailing_slash(self):
        """Test that trailing slashes are handled."""
        client = GarageAdminClient(
            admin_endpoint="http://localhost:3903/",
            admin_token="test-token",
        )
        assert client.admin_endpoint == "http://localhost:3903"

    @patch("requests.Session")
    def test_health_check(self, mock_session_class):
        """Test health check request."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "healthy"}
        mock_response.content = b'{"status": "healthy"}'
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = GarageAdminClient(
            admin_endpoint="http://localhost:3903",
            admin_token="test-token",
        )
        client.session = mock_session

        result = client.health_check()

        mock_session.request.assert_called_once()
        assert result == {"status": "healthy"}

    @patch("requests.Session")
    def test_list_buckets(self, mock_session_class):
        """Test listing buckets."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "bucket1", "globalAliases": ["my-bucket"]},
        ]
        mock_response.content = b'[{"id": "bucket1"}]'
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = GarageAdminClient(
            admin_endpoint="http://localhost:3903",
            admin_token="test-token",
        )
        client.session = mock_session

        result = client.list_buckets()

        assert isinstance(result, list)
        assert len(result) == 1

    @patch("requests.Session")
    def test_create_bucket(self, mock_session_class):
        """Test bucket creation."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "new-bucket-id",
            "globalAliases": ["test-bucket"],
        }
        mock_response.content = b'{"id": "new-bucket-id"}'
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = GarageAdminClient(
            admin_endpoint="http://localhost:3903",
            admin_token="test-token",
        )
        client.session = mock_session

        result = client.create_bucket(global_alias="test-bucket")

        assert result["id"] == "new-bucket-id"

    @patch("requests.Session")
    def test_create_key(self, mock_session_class):
        """Test key creation."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "accessKeyId": "GK123",
            "secretAccessKey": "secret123",
            "name": "test-key",
        }
        mock_response.content = b'{"accessKeyId": "GK123"}'
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = GarageAdminClient(
            admin_endpoint="http://localhost:3903",
            admin_token="test-token",
        )
        client.session = mock_session

        result = client.create_key(name="test-key")

        assert result["accessKeyId"] == "GK123"
        assert result["secretAccessKey"] == "secret123"

    @patch("requests.Session")
    def test_allow_key_on_bucket(self, mock_session_class):
        """Test granting key access to bucket."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.content = b'{"success": true}'
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = GarageAdminClient(
            admin_endpoint="http://localhost:3903",
            admin_token="test-token",
        )
        client.session = mock_session

        result = client.allow_key_on_bucket(
            bucket_id="bucket123",
            access_key_id="GK123",
            read=True,
            write=True,
            owner=False,
        )

        call_args = mock_session.request.call_args
        assert call_args[1]["json"]["accessKeyId"] == "GK123"
        assert call_args[1]["json"]["permissions"]["read"] is True


class TestClientRetry:
    """Tests for retry behavior."""

    @patch("requests.Session")
    @patch("time.sleep")
    def test_retry_on_failure(self, mock_sleep, mock_session_class):
        """Test that requests are retried on failure."""
        import requests

        mock_session = MagicMock()
        mock_session.request.side_effect = [
            requests.RequestException("Connection failed"),
            requests.RequestException("Connection failed"),
            MagicMock(json=lambda: {"status": "ok"}, content=b'{"status": "ok"}'),
        ]
        mock_session_class.return_value = mock_session

        client = GarageAdminClient(
            admin_endpoint="http://localhost:3903",
            admin_token="test-token",
            retry_attempts=3,
        )
        client.session = mock_session

        result = client.health_check()

        assert mock_session.request.call_count == 3
        assert result == {"status": "ok"}
