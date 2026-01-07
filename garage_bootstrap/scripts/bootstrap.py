#!/usr/bin/env python3
"""
Main entry point for the Garage Bootstrap service.

This script handles cluster initialization and bootstrapping based on
configuration from environment variables or config files.
"""

import argparse
import json
import logging
import os
import sys

from garage_bootstrap.admin_client import GarageAdminClient
from garage_bootstrap.bootstrap import (
    GarageBootstrap,
    load_config_from_env,
    load_config_from_file,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Bootstrap a Garage S3 cluster with declarative configuration"
    )
    parser.add_argument(
        "--config",
        "-c",
        help="Path to configuration file (YAML or JSON)",
    )
    parser.add_argument(
        "--endpoint",
        "-e",
        default=os.environ.get("GARAGE_ADMIN_ENDPOINT", "http://localhost:3903"),
        help="Garage admin API endpoint",
    )
    parser.add_argument(
        "--token",
        "-t",
        default=os.environ.get("GARAGE_ADMIN_TOKEN"),
        help="Garage admin token",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Don't wait for cluster to be ready",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Timeout for waiting for cluster (seconds)",
    )
    parser.add_argument(
        "--output",
        "-o",
        choices=["json", "text"],
        default="text",
        help="Output format",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.token:
        logger.error("Admin token is required. Set GARAGE_ADMIN_TOKEN or use --token")
        sys.exit(1)

    try:
        # Create client
        client = GarageAdminClient(
            admin_endpoint=args.endpoint,
            admin_token=args.token,
        )

        # Load configuration
        if args.config:
            config = load_config_from_file(args.config)
        else:
            config = load_config_from_env()

        # Bootstrap cluster
        bootstrap = GarageBootstrap(client)

        if not args.no_wait:
            logger.info(f"Waiting for Garage cluster to be ready (timeout: {args.timeout}s)...")
            client.wait_for_ready(timeout=args.timeout)

        result = bootstrap.bootstrap(config, wait_for_ready=False)

        # Output result
        if args.output == "json":
            print(json.dumps(result, indent=2))
        else:
            print("\n=== Bootstrap Complete ===\n")

            if result.get("layout_applied"):
                print("✓ Layout applied")

            if result.get("keys"):
                print(f"\nKeys ({len(result['keys'])}):")
                for key in result["keys"]:
                    status = "created" if key.get("created") else "existing"
                    print(f"  - {key['name']} ({status})")
                    if key.get("secretAccessKey"):
                        print(f"    Access Key ID: {key['accessKeyId']}")
                        print(f"    Secret Key: {key['secretAccessKey']}")

            if result.get("buckets"):
                print(f"\nBuckets ({len(result['buckets'])}):")
                for bucket in result["buckets"]:
                    status = "created" if bucket.get("created") else "existing"
                    print(f"  - {bucket['name']} ({status})")

        logger.info("Bootstrap completed successfully")

    except Exception as e:
        logger.error(f"Bootstrap failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
