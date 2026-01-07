"""
Garage Admin API Client

Provides a Python interface to the Garage admin API for cluster management,
bucket creation, and access key management.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)


class GarageAdminClient:
    """Client for interacting with the Garage admin API."""

    def __init__(
        self,
        admin_endpoint: str,
        admin_token: str,
        timeout: int = 30,
        retry_attempts: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        Initialize the Garage admin client.

        Args:
            admin_endpoint: The URL of the Garage admin API (e.g., http://garage:3903)
            admin_token: The admin token for authentication
            timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts for failed requests
            retry_delay: Delay between retries in seconds
        """
        self.admin_endpoint = admin_endpoint.rstrip("/")
        self.admin_token = admin_token
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {admin_token}",
                "Content-Type": "application/json",
            }
        )

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Make a request to the admin API with retries.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            data: Request body data
            params: Query parameters

        Returns:
            Response data as a dictionary

        Raises:
            requests.RequestException: If all retry attempts fail
        """
        url = urljoin(self.admin_endpoint + "/", endpoint.lstrip("/"))

        for attempt in range(self.retry_attempts):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params,
                    timeout=self.timeout,
                )
                response.raise_for_status()

                if response.content:
                    return response.json()
                return {}

            except requests.RequestException as e:
                if attempt < self.retry_attempts - 1:
                    logger.warning(
                        f"Request to {url} failed (attempt {attempt + 1}): {e}"
                    )
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    logger.error(f"Request to {url} failed after {self.retry_attempts} attempts")
                    raise

    def health_check(self) -> Dict[str, Any]:
        """
        Check the health status of the Garage cluster.

        Returns:
            Health status information
        """
        return self._request("GET", "/health")

    def get_cluster_status(self) -> Dict[str, Any]:
        """
        Get the current cluster status.

        Returns:
            Cluster status information
        """
        return self._request("GET", "/v2/cluster")

    def get_layout(self) -> Dict[str, Any]:
        """
        Get the current cluster layout.

        Returns:
            Current layout configuration
        """
        return self._request("GET", "/v2/layout")

    def apply_layout(self, version: int) -> Dict[str, Any]:
        """
        Apply the staged layout changes.

        Args:
            version: The new layout version number

        Returns:
            Result of the layout application
        """
        return self._request("POST", "/v2/layout/apply", data={"version": version})

    def revert_layout(self) -> Dict[str, Any]:
        """
        Revert any staged layout changes.

        Returns:
            Result of the layout reversion
        """
        return self._request("POST", "/v2/layout/revert")

    def update_layout(
        self,
        node_id: str,
        zone: str,
        capacity: Optional[int] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Update the layout for a specific node.

        Args:
            node_id: The node ID to update
            zone: The zone for the node
            capacity: Storage capacity in bytes (None to remove from layout)
            tags: Optional tags for the node

        Returns:
            Result of the layout update
        """
        node_config = {"zone": zone}
        if capacity is not None:
            node_config["capacity"] = capacity
        if tags:
            node_config["tags"] = tags

        return self._request("POST", "/v2/layout", data={node_id: node_config})

    # Bucket Operations
    def list_buckets(self) -> List[Dict[str, Any]]:
        """
        List all buckets in the cluster.

        Returns:
            List of bucket information
        """
        return self._request("GET", "/v2/buckets")

    def get_bucket(self, bucket_id: str) -> Dict[str, Any]:
        """
        Get information about a specific bucket.

        Args:
            bucket_id: The bucket ID or global alias

        Returns:
            Bucket information
        """
        return self._request("GET", f"/v2/buckets/{bucket_id}")

    def create_bucket(self, global_alias: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new bucket.

        Args:
            global_alias: Optional global alias for the bucket

        Returns:
            Created bucket information
        """
        data = {}
        if global_alias:
            data["globalAlias"] = global_alias
        return self._request("POST", "/v2/buckets", data=data)

    def delete_bucket(self, bucket_id: str) -> Dict[str, Any]:
        """
        Delete a bucket.

        Args:
            bucket_id: The bucket ID to delete

        Returns:
            Deletion result
        """
        return self._request("DELETE", f"/v2/buckets/{bucket_id}")

    def update_bucket(
        self,
        bucket_id: str,
        website_access: Optional[Dict] = None,
        quotas: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Update bucket settings.

        Args:
            bucket_id: The bucket ID to update
            website_access: Website access configuration
            quotas: Quota configuration

        Returns:
            Updated bucket information
        """
        data = {}
        if website_access is not None:
            data["websiteAccess"] = website_access
        if quotas is not None:
            data["quotas"] = quotas
        return self._request("PUT", f"/v2/buckets/{bucket_id}", data=data)

    def add_bucket_alias(
        self, bucket_id: str, alias: str, is_global: bool = True
    ) -> Dict[str, Any]:
        """
        Add an alias to a bucket.

        Args:
            bucket_id: The bucket ID
            alias: The alias to add
            is_global: Whether the alias is global

        Returns:
            Result of the alias addition
        """
        endpoint = f"/v2/buckets/{bucket_id}/aliases"
        params = {"alias": alias}
        if is_global:
            params["global"] = "true"
        return self._request("PUT", endpoint, params=params)

    def remove_bucket_alias(
        self, bucket_id: str, alias: str, is_global: bool = True
    ) -> Dict[str, Any]:
        """
        Remove an alias from a bucket.

        Args:
            bucket_id: The bucket ID
            alias: The alias to remove
            is_global: Whether the alias is global

        Returns:
            Result of the alias removal
        """
        endpoint = f"/v2/buckets/{bucket_id}/aliases"
        params = {"alias": alias}
        if is_global:
            params["global"] = "true"
        return self._request("DELETE", endpoint, params=params)

    # Key Operations
    def list_keys(self) -> List[Dict[str, Any]]:
        """
        List all access keys.

        Returns:
            List of access key information
        """
        return self._request("GET", "/v2/keys")

    def get_key(self, key_id: str) -> Dict[str, Any]:
        """
        Get information about a specific access key.

        Args:
            key_id: The access key ID

        Returns:
            Access key information
        """
        return self._request("GET", f"/v2/keys/{key_id}")

    def create_key(self, name: str) -> Dict[str, Any]:
        """
        Create a new access key.

        Args:
            name: Name for the access key

        Returns:
            Created access key information including:
            - accessKeyId: The access key ID
            - secretAccessKey: The secret key (SENSITIVE - handle securely, do not log)
            - name: The key name

        Warning:
            The secretAccessKey is only returned during key creation.
            Store it securely - it cannot be retrieved again.
        """
        return self._request("POST", "/v2/keys", data={"name": name})

    def delete_key(self, key_id: str) -> Dict[str, Any]:
        """
        Delete an access key.

        Args:
            key_id: The access key ID to delete

        Returns:
            Deletion result
        """
        return self._request("DELETE", f"/v2/keys/{key_id}")

    def update_key(
        self,
        key_id: str,
        name: Optional[str] = None,
        allow_create_bucket: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Update access key settings.

        Args:
            key_id: The access key ID
            name: New name for the key
            allow_create_bucket: Whether the key can create buckets

        Returns:
            Updated access key information
        """
        data = {}
        if name is not None:
            data["name"] = name
        if allow_create_bucket is not None:
            data["allow"] = {"createBucket": allow_create_bucket}
        return self._request("POST", f"/v2/keys/{key_id}", data=data)

    def allow_key_on_bucket(
        self,
        bucket_id: str,
        access_key_id: str,
        read: bool = True,
        write: bool = True,
        owner: bool = False,
    ) -> Dict[str, Any]:
        """
        Grant bucket access to an access key.

        Args:
            bucket_id: The bucket ID
            access_key_id: The access key ID
            read: Allow read access
            write: Allow write access
            owner: Grant owner permissions

        Returns:
            Result of the permission grant
        """
        return self._request(
            "POST",
            f"/v2/buckets/{bucket_id}/allow_key",
            data={
                "accessKeyId": access_key_id,
                "permissions": {"read": read, "write": write, "owner": owner},
            },
        )

    def deny_key_on_bucket(self, bucket_id: str, access_key_id: str) -> Dict[str, Any]:
        """
        Revoke bucket access from an access key.

        Args:
            bucket_id: The bucket ID
            access_key_id: The access key ID

        Returns:
            Result of the permission revocation
        """
        return self._request(
            "POST",
            f"/v2/buckets/{bucket_id}/deny_key",
            data={"accessKeyId": access_key_id},
        )

    def find_or_create_key(self, name: str) -> Dict[str, Any]:
        """
        Find an existing key by name or create a new one.

        Args:
            name: Name of the key to find or create

        Returns:
            Key information (note: secretAccessKey only available for new keys)
        """
        keys = self.list_keys()
        for key in keys:
            if key.get("name") == name:
                return self.get_key(key["id"])
        return self.create_key(name)

    def find_or_create_bucket(self, global_alias: str) -> Dict[str, Any]:
        """
        Find an existing bucket by alias or create a new one.

        Args:
            global_alias: Global alias for the bucket

        Returns:
            Bucket information
        """
        buckets = self.list_buckets()
        for bucket in buckets:
            if global_alias in bucket.get("globalAliases", []):
                return self.get_bucket(bucket["id"])
        return self.create_bucket(global_alias=global_alias)

    def wait_for_ready(
        self, timeout: int = 120, check_interval: float = 2.0
    ) -> bool:
        """
        Wait for the Garage cluster to be ready.

        Args:
            timeout: Maximum time to wait in seconds
            check_interval: Time between health checks

        Returns:
            True if cluster is ready, False if timeout

        Raises:
            TimeoutError: If the cluster doesn't become ready within timeout
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                health = self.health_check()
                if health:
                    logger.info("Garage cluster is ready")
                    return True
            except Exception as e:
                logger.debug(f"Health check failed: {e}")
            time.sleep(check_interval)

        raise TimeoutError(f"Garage cluster not ready after {timeout} seconds")
