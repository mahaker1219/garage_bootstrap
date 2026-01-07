#!/usr/bin/env python3
"""
Connectivity Test CLI for Garage S3 Storage.

This script allows you to test S3 connectivity against a live Garage cluster
using multiple client libraries (MinIO, boto3, Azure Blob Storage).

Usage:
    python -m garage_bootstrap.scripts.test_connectivity
    python -m garage_bootstrap.scripts.test_connectivity --library minio
    python -m garage_bootstrap.scripts.test_connectivity --endpoint localhost:3900 --access-key GK... --secret-key ...
"""

import argparse
import json
import logging
import os
import sys
from typing import Dict, Any, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from garage_bootstrap.connectivity import (
    MinioConnectivityTest,
    S3ConnectivityTest,
    AzureBlobConnectivityTest,
    run_all_connectivity_tests,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_test_config_from_env() -> Dict[str, Any]:
    """Get test configuration from environment variables."""
    return {
        "endpoint": os.environ.get("GARAGE_S3_ENDPOINT", "localhost:3900"),
        "access_key": os.environ.get("TEST_ACCESS_KEY", ""),
        "secret_key": os.environ.get("TEST_SECRET_KEY", ""),
        "bucket": os.environ.get("TEST_BUCKET", "test-bucket"),
        "region": os.environ.get("TEST_REGION", "garage"),
        "secure": os.environ.get("TEST_SECURE", "false").lower() == "true",
    }


def run_single_library_test(
    library: str,
    config: Dict[str, Any],
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Run connectivity test for a single library.

    Args:
        library: Library name (minio, s3, azure)
        config: Test configuration
        verbose: Enable verbose output

    Returns:
        Test results dictionary
    """
    test_classes = {
        "minio": MinioConnectivityTest,
        "s3": S3ConnectivityTest,
        "azure": AzureBlobConnectivityTest,
    }

    if library not in test_classes:
        return {"success": False, "error": f"Unknown library: {library}"}

    try:
        test_class = test_classes[library]
        test = test_class(
            endpoint=config["endpoint"],
            access_key=config["access_key"],
            secret_key=config["secret_key"],
            bucket=config["bucket"],
            region=config["region"],
            secure=config["secure"],
        )
        return test.run_full_test()
    except ImportError as e:
        return {"success": False, "error": f"Library not installed: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def print_results_text(results: Dict[str, Any], verbose: bool = False):
    """Print test results in human-readable format."""
    print("\n" + "=" * 60)
    print("GARAGE S3 CONNECTIVITY TEST RESULTS")
    print("=" * 60)

    if "libraries" in results:
        # Multiple libraries
        for lib_name, lib_result in results["libraries"].items():
            print(f"\n📦 {lib_name.upper()}")
            print("-" * 40)

            if lib_result.get("success"):
                print("  ✅ Overall: PASSED")
            else:
                print("  ❌ Overall: FAILED")

            if "error" in lib_result:
                print(f"  Error: {lib_result['error']}")
            elif "tests" in lib_result:
                for test_name, test_result in lib_result["tests"].items():
                    if test_name.endswith("_error"):
                        continue
                    status = "✅" if test_result else "❌"
                    print(f"    {status} {test_name}")
                    if verbose and f"{test_name}_error" in lib_result["tests"]:
                        print(f"       Error: {lib_result['tests'][f'{test_name}_error']}")

        print("\n" + "=" * 60)
        if results.get("overall_success"):
            print("🎉 ALL TESTS PASSED")
        else:
            print("⚠️  SOME TESTS FAILED")
        print("=" * 60)
    else:
        # Single library
        if results.get("success"):
            print("  ✅ Overall: PASSED")
        else:
            print("  ❌ Overall: FAILED")

        if "error" in results:
            print(f"  Error: {results['error']}")
        elif "tests" in results:
            for test_name, test_result in results["tests"].items():
                if test_name.endswith("_error"):
                    continue
                status = "✅" if test_result else "❌"
                print(f"  {status} {test_name}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test S3 connectivity against a live Garage cluster",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  GARAGE_S3_ENDPOINT    S3 endpoint (default: localhost:3900)
  TEST_ACCESS_KEY       Access key ID
  TEST_SECRET_KEY       Secret access key
  TEST_BUCKET           Bucket name for testing (default: test-bucket)
  TEST_REGION           Region name (default: garage)
  TEST_SECURE           Use HTTPS (true/false, default: false)

Examples:
  # Run all tests with environment variables
  python -m garage_bootstrap.scripts.test_connectivity

  # Run specific library test
  python -m garage_bootstrap.scripts.test_connectivity --library minio

  # Run with explicit parameters
  python -m garage_bootstrap.scripts.test_connectivity \\
      --endpoint localhost:3900 \\
      --access-key GKxxxxxxxxxxxxxxxxxx \\
      --secret-key yoursecretkey \\
      --bucket test-bucket
        """,
    )

    parser.add_argument(
        "--endpoint",
        "-e",
        help="S3 endpoint (host:port or URL)",
    )
    parser.add_argument(
        "--access-key",
        "-a",
        help="Access key ID",
    )
    parser.add_argument(
        "--secret-key",
        "-s",
        help="Secret access key",
    )
    parser.add_argument(
        "--bucket",
        "-b",
        help="Bucket name for testing",
    )
    parser.add_argument(
        "--region",
        "-r",
        default="garage",
        help="Region name (default: garage)",
    )
    parser.add_argument(
        "--secure",
        action="store_true",
        help="Use HTTPS",
    )
    parser.add_argument(
        "--library",
        "-l",
        choices=["minio", "s3", "azure", "all"],
        default="all",
        help="Library to test (default: all)",
    )
    parser.add_argument(
        "--output",
        "-o",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Build configuration from args and environment
    config = get_test_config_from_env()

    if args.endpoint:
        config["endpoint"] = args.endpoint
    if args.access_key:
        config["access_key"] = args.access_key
    if args.secret_key:
        config["secret_key"] = args.secret_key
    if args.bucket:
        config["bucket"] = args.bucket
    if args.region:
        config["region"] = args.region
    if args.secure:
        config["secure"] = True

    # Validate required parameters
    if not config["access_key"]:
        print("Error: Access key is required. Set TEST_ACCESS_KEY or use --access-key")
        sys.exit(1)
    if not config["secret_key"]:
        print("Error: Secret key is required. Set TEST_SECRET_KEY or use --secret-key")
        sys.exit(1)

    print(f"\nTesting connectivity to: {config['endpoint']}")
    print(f"Bucket: {config['bucket']}")
    print(f"Region: {config['region']}")
    print(f"Secure: {config['secure']}")

    # Run tests
    if args.library == "all":
        results = run_all_connectivity_tests(
            endpoint=config["endpoint"],
            access_key=config["access_key"],
            secret_key=config["secret_key"],
            bucket=config["bucket"],
            region=config["region"],
            secure=config["secure"],
        )
    else:
        results = run_single_library_test(args.library, config, args.verbose)

    # Output results
    if args.output == "json":
        print(json.dumps(results, indent=2, default=str))
    else:
        print_results_text(results, args.verbose)

    # Exit with appropriate code
    success = results.get("overall_success", results.get("success", False))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
