#!/usr/bin/env python3
"""
Version update script for Garage Bootstrap.

This script ensures that the Docker image tag and Helm chart appVersion
are synchronized. It updates:
- Chart.yaml appVersion
- Chart.yaml version (optionally)
- values.yaml image tag

Usage:
    ./scripts/update_version.py --version 1.0.0
    ./scripts/update_version.py --version 1.0.0 --chart-version 0.2.0
"""

import argparse
import re
import sys
from pathlib import Path


def update_chart_yaml(chart_path: Path, app_version: str, chart_version: str = None) -> bool:
    """
    Update Chart.yaml with new versions using regex to preserve formatting.

    Args:
        chart_path: Path to Chart.yaml
        app_version: New appVersion
        chart_version: New chart version (optional)

    Returns:
        True if updated successfully
    """
    if not chart_path.exists():
        print(f"Error: Chart.yaml not found at {chart_path}")
        return False

    with open(chart_path, "r") as f:
        content = f.read()

    # Update appVersion (preserve quotes if present)
    content = re.sub(
        r'(appVersion:\s*)["\']?[^"\'\n]+["\']?',
        f'\\1"{app_version}"',
        content,
    )

    if chart_version:
        # Update version
        content = re.sub(
            r'(^version:\s*)[^\n]+',
            f'\\g<1>{chart_version}',
            content,
            flags=re.MULTILINE,
        )

    with open(chart_path, "w") as f:
        f.write(content)

    print(f"Updated Chart.yaml:")
    print(f"  appVersion: {app_version}")
    if chart_version:
        print(f"  version: {chart_version}")

    return True


def update_values_yaml(values_path: Path, image_tag: str) -> bool:
    """
    Update values.yaml with new image tag using regex to preserve formatting.

    Args:
        values_path: Path to values.yaml
        image_tag: New image tag

    Returns:
        True if updated successfully
    """
    if not values_path.exists():
        print(f"Error: values.yaml not found at {values_path}")
        return False

    with open(values_path, "r") as f:
        content = f.read()

    # Update tag under bootstrap.image section
    # Match tag: "value" or tag: 'value' or tag: value
    content = re.sub(
        r'(image:\s*\n\s*repository:[^\n]+\n\s*tag:\s*)["\']?[^"\'\n]+["\']?',
        f'\\1"{image_tag}"',
        content,
    )

    with open(values_path, "w") as f:
        f.write(content)

    print(f"Updated values.yaml bootstrap.image.tag: {image_tag}")
    return True


def update_init_version(init_path: Path, version: str) -> bool:
    """
    Update __init__.py version string.

    Args:
        init_path: Path to __init__.py
        version: New version string

    Returns:
        True if updated successfully
    """
    if not init_path.exists():
        print(f"Error: __init__.py not found at {init_path}")
        return False

    with open(init_path, "r") as f:
        content = f.read()

    # Update __version__ string
    new_content = re.sub(
        r'__version__\s*=\s*["\'][^"\']+["\']',
        f'__version__ = "{version}"',
        content,
    )

    with open(init_path, "w") as f:
        f.write(new_content)

    print(f"Updated __init__.py __version__: {version}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Update version strings across the project"
    )
    parser.add_argument(
        "--version",
        "-v",
        required=True,
        help="Version/tag to set (e.g., 1.0.0, v1.0.0)",
    )
    parser.add_argument(
        "--chart-version",
        "-c",
        help="Helm chart version (optional, defaults to same as --version)",
    )
    parser.add_argument(
        "--chart-dir",
        default="chart",
        help="Path to chart directory (default: chart)",
    )
    parser.add_argument(
        "--src-dir",
        default="garage_bootstrap",
        help="Path to source directory (default: garage_bootstrap)",
    )

    args = parser.parse_args()

    # Normalize version (remove 'v' prefix if present for appVersion)
    version = args.version.lstrip("v")
    chart_version = args.chart_version.lstrip("v") if args.chart_version else version

    # Find project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    # Update Chart.yaml
    chart_yaml = project_root / args.chart_dir / "Chart.yaml"
    if chart_yaml.exists():
        update_chart_yaml(chart_yaml, version, chart_version)
    else:
        print(f"Warning: Chart.yaml not found at {chart_yaml}")

    # Update values.yaml
    values_yaml = project_root / args.chart_dir / "values.yaml"
    if values_yaml.exists():
        update_values_yaml(values_yaml, args.version)  # Keep original tag format
    else:
        print(f"Warning: values.yaml not found at {values_yaml}")

    # Update __init__.py
    init_py = project_root / args.src_dir / "__init__.py"
    if init_py.exists():
        update_init_version(init_py, version)
    else:
        print(f"Warning: __init__.py not found at {init_py}")

    print(f"\nVersion update complete: {args.version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
