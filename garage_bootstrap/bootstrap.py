"""
Garage Cluster Bootstrap

Provides functionality for declaratively bootstrapping a Garage cluster
including layout configuration, bucket creation, and access key management.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import yaml

from .admin_client import GarageAdminClient

logger = logging.getLogger(__name__)


@dataclass
class BucketConfig:
    """Configuration for a bucket to be created."""

    name: str
    quotas: Optional[Dict[str, Any]] = None
    website_access: Optional[Dict[str, Any]] = None
    keys: List[str] = field(default_factory=list)
    permissions: Dict[str, Dict[str, bool]] = field(default_factory=dict)


@dataclass
class KeyConfig:
    """Configuration for an access key to be created."""

    name: str
    allow_create_bucket: bool = False


@dataclass
class LayoutNodeConfig:
    """Configuration for a node in the cluster layout."""

    node_id: str
    zone: str
    capacity: Optional[int] = None
    tags: Optional[List[str]] = None


@dataclass
class ClusterConfig:
    """Complete cluster configuration."""

    buckets: List[BucketConfig] = field(default_factory=list)
    keys: List[KeyConfig] = field(default_factory=list)
    layout: List[LayoutNodeConfig] = field(default_factory=list)
    apply_layout: bool = True


def load_config_from_file(config_path: str) -> ClusterConfig:
    """
    Load cluster configuration from a YAML or JSON file.

    Args:
        config_path: Path to the configuration file

    Returns:
        Parsed ClusterConfig object
    """
    with open(config_path, "r") as f:
        if config_path.endswith((".yml", ".yaml")):
            data = yaml.safe_load(f)
        else:
            data = json.load(f)

    return parse_config(data)


def load_config_from_env() -> ClusterConfig:
    """
    Load cluster configuration from environment variables.

    Environment variables:
        GARAGE_BOOTSTRAP_CONFIG: JSON string with full configuration
        GARAGE_BUCKETS: Comma-separated list of bucket names
        GARAGE_KEYS: Comma-separated list of key names

    Returns:
        Parsed ClusterConfig object
    """
    # Check for full config in environment
    config_json = os.environ.get("GARAGE_BOOTSTRAP_CONFIG")
    if config_json:
        data = json.loads(config_json)
        return parse_config(data)

    # Parse simple environment variables
    buckets = []
    bucket_names = os.environ.get("GARAGE_BUCKETS", "").split(",")
    for name in bucket_names:
        name = name.strip()
        if name:
            buckets.append(BucketConfig(name=name))

    keys = []
    key_names = os.environ.get("GARAGE_KEYS", "").split(",")
    for name in key_names:
        name = name.strip()
        if name:
            keys.append(KeyConfig(name=name))

    return ClusterConfig(buckets=buckets, keys=keys)


def parse_config(data: Dict[str, Any]) -> ClusterConfig:
    """
    Parse a configuration dictionary into a ClusterConfig object.

    Args:
        data: Configuration dictionary

    Returns:
        ClusterConfig object
    """
    buckets = []
    for bucket_data in data.get("buckets", []):
        if isinstance(bucket_data, str):
            buckets.append(BucketConfig(name=bucket_data))
        else:
            buckets.append(
                BucketConfig(
                    name=bucket_data["name"],
                    quotas=bucket_data.get("quotas"),
                    website_access=bucket_data.get("websiteAccess"),
                    keys=bucket_data.get("keys", []),
                    permissions=bucket_data.get("permissions", {}),
                )
            )

    keys = []
    for key_data in data.get("keys", []):
        if isinstance(key_data, str):
            keys.append(KeyConfig(name=key_data))
        else:
            keys.append(
                KeyConfig(
                    name=key_data["name"],
                    allow_create_bucket=key_data.get("allowCreateBucket", False),
                )
            )

    layout = []
    for node_data in data.get("layout", []):
        layout.append(
            LayoutNodeConfig(
                node_id=node_data["nodeId"],
                zone=node_data["zone"],
                capacity=node_data.get("capacity"),
                tags=node_data.get("tags"),
            )
        )

    return ClusterConfig(
        buckets=buckets,
        keys=keys,
        layout=layout,
        apply_layout=data.get("applyLayout", True),
    )


class GarageBootstrap:
    """Bootstrap a Garage cluster with declarative configuration."""

    def __init__(self, client: GarageAdminClient):
        """
        Initialize the bootstrap manager.

        Args:
            client: GarageAdminClient instance
        """
        self.client = client
        self.created_keys: Dict[str, Dict[str, Any]] = {}
        self.created_buckets: Dict[str, Dict[str, Any]] = {}

    def bootstrap(
        self, config: ClusterConfig, wait_for_ready: bool = True
    ) -> Dict[str, Any]:
        """
        Bootstrap the cluster with the given configuration.

        Args:
            config: Cluster configuration
            wait_for_ready: Whether to wait for cluster to be ready first

        Returns:
            Dictionary with created resources information
        """
        if wait_for_ready:
            logger.info("Waiting for Garage cluster to be ready...")
            self.client.wait_for_ready()

        result = {
            "layout_applied": False,
            "keys": [],
            "buckets": [],
        }

        # Apply layout if configured
        if config.layout:
            result["layout_applied"] = self._apply_layout(config.layout, config.apply_layout)

        # Create keys first (buckets may reference them)
        for key_config in config.keys:
            key_info = self._ensure_key(key_config)
            result["keys"].append(key_info)

        # Create buckets and set up permissions
        for bucket_config in config.buckets:
            bucket_info = self._ensure_bucket(bucket_config)
            result["buckets"].append(bucket_info)

        return result

    def _apply_layout(
        self, layout_config: List[LayoutNodeConfig], apply: bool = True
    ) -> bool:
        """
        Configure and optionally apply the cluster layout.

        Args:
            layout_config: List of node configurations
            apply: Whether to apply the layout after staging

        Returns:
            True if layout was applied
        """
        logger.info("Configuring cluster layout...")

        for node_config in layout_config:
            logger.info(f"Configuring node {node_config.node_id} in zone {node_config.zone}")
            self.client.update_layout(
                node_id=node_config.node_id,
                zone=node_config.zone,
                capacity=node_config.capacity,
                tags=node_config.tags,
            )

        if apply:
            current_layout = self.client.get_layout()
            current_version = current_layout.get("version", 0)
            new_version = current_version + 1
            logger.info(f"Applying layout version {new_version}")
            self.client.apply_layout(new_version)
            return True

        return False

    def _ensure_key(self, key_config: KeyConfig) -> Dict[str, Any]:
        """
        Ensure an access key exists with the specified configuration.

        Args:
            key_config: Key configuration

        Returns:
            Key information
        """
        logger.info(f"Ensuring key exists: {key_config.name}")

        # Check if key already exists
        existing_keys = self.client.list_keys()
        for key in existing_keys:
            if key.get("name") == key_config.name:
                key_info = self.client.get_key(key["id"])
                self.created_keys[key_config.name] = key_info
                logger.info(f"Key already exists: {key_config.name}")
                return {
                    "name": key_config.name,
                    "accessKeyId": key_info["accessKeyId"],
                    "created": False,
                }

        # Create new key
        key_info = self.client.create_key(key_config.name)
        self.created_keys[key_config.name] = key_info

        # Update key settings if needed
        if key_config.allow_create_bucket:
            self.client.update_key(
                key_info["accessKeyId"],
                allow_create_bucket=True,
            )

        logger.info(f"Created key: {key_config.name}")
        return {
            "name": key_config.name,
            "accessKeyId": key_info["accessKeyId"],
            "secretAccessKey": key_info.get("secretAccessKey"),
            "created": True,
        }

    def _ensure_bucket(self, bucket_config: BucketConfig) -> Dict[str, Any]:
        """
        Ensure a bucket exists with the specified configuration.

        Args:
            bucket_config: Bucket configuration

        Returns:
            Bucket information
        """
        logger.info(f"Ensuring bucket exists: {bucket_config.name}")

        # Check if bucket already exists
        bucket_info = self.client.find_or_create_bucket(bucket_config.name)
        bucket_id = bucket_info["id"]
        created = not bucket_info.get("globalAliases")

        self.created_buckets[bucket_config.name] = bucket_info

        # Apply bucket settings
        if bucket_config.quotas or bucket_config.website_access:
            self.client.update_bucket(
                bucket_id,
                website_access=bucket_config.website_access,
                quotas=bucket_config.quotas,
            )

        # Set up key permissions
        for key_name in bucket_config.keys:
            permissions = bucket_config.permissions.get(
                key_name, {"read": True, "write": True, "owner": False}
            )

            # Get key ID
            key_info = self.created_keys.get(key_name)
            if not key_info:
                key_info = self.client.find_or_create_key(key_name)
                self.created_keys[key_name] = key_info

            key_id = key_info.get("accessKeyId") or key_info.get("id")

            logger.info(f"Granting {key_name} access to bucket {bucket_config.name}")
            self.client.allow_key_on_bucket(
                bucket_id=bucket_id,
                access_key_id=key_id,
                **permissions,
            )

        return {
            "name": bucket_config.name,
            "id": bucket_id,
            "created": created,
        }


def bootstrap_from_config_file(
    admin_endpoint: str,
    admin_token: str,
    config_path: str,
    wait_for_ready: bool = True,
) -> Dict[str, Any]:
    """
    Bootstrap a Garage cluster from a configuration file.

    Args:
        admin_endpoint: Garage admin API endpoint
        admin_token: Admin authentication token
        config_path: Path to configuration file
        wait_for_ready: Wait for cluster to be ready

    Returns:
        Bootstrap result
    """
    client = GarageAdminClient(admin_endpoint, admin_token)
    config = load_config_from_file(config_path)
    bootstrap = GarageBootstrap(client)
    return bootstrap.bootstrap(config, wait_for_ready)


def bootstrap_from_env(
    wait_for_ready: bool = True,
) -> Dict[str, Any]:
    """
    Bootstrap a Garage cluster from environment variables.

    Environment variables:
        GARAGE_ADMIN_ENDPOINT: Admin API endpoint
        GARAGE_ADMIN_TOKEN: Admin authentication token
        GARAGE_BOOTSTRAP_CONFIG: JSON configuration (optional)
        GARAGE_BUCKETS: Comma-separated bucket names (optional)
        GARAGE_KEYS: Comma-separated key names (optional)

    Returns:
        Bootstrap result
    """
    admin_endpoint = os.environ["GARAGE_ADMIN_ENDPOINT"]
    admin_token = os.environ["GARAGE_ADMIN_TOKEN"]

    client = GarageAdminClient(admin_endpoint, admin_token)
    config = load_config_from_env()
    bootstrap = GarageBootstrap(client)
    return bootstrap.bootstrap(config, wait_for_ready)
