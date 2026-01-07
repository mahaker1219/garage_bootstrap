"""
Data loader/exporter module for Garage S3 storage.

Provides functionality to backup and restore all objects in an S3-compatible
object store at the application level, independent of PVC-based storage.
"""

import hashlib
import io
import json
import logging
import os
import tarfile
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)


@dataclass
class ObjectInfo:
    """Information about an S3 object."""

    key: str
    size: int
    etag: str
    last_modified: datetime
    content_type: Optional[str] = None
    metadata: Optional[Dict[str, str]] = None


@dataclass
class BackupManifest:
    """Manifest for a backup archive."""

    version: str
    created_at: str
    bucket: str
    total_objects: int
    total_size: int
    objects: List[Dict[str, Any]]


class DataManager:
    """Manages data backup and restore operations for S3-compatible storage."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        region: str = "garage",
        secure: bool = False,
        max_workers: int = 4,
    ):
        """
        Initialize the data manager.

        Args:
            endpoint: S3 endpoint URL
            access_key: Access key ID
            secret_key: Secret access key
            region: Region name
            secure: Use HTTPS
            max_workers: Maximum concurrent operations
        """
        self.endpoint = endpoint
        if not endpoint.startswith(("http://", "https://")):
            protocol = "https" if secure else "http"
            self.endpoint = f"{protocol}://{endpoint}"

        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.max_workers = max_workers

        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        )

    def list_buckets(self) -> List[str]:
        """
        List all buckets.

        Returns:
            List of bucket names
        """
        response = self.client.list_buckets()
        return [b["Name"] for b in response.get("Buckets", [])]

    def list_objects(
        self, bucket: str, prefix: str = "", max_keys: int = 1000
    ) -> Iterator[ObjectInfo]:
        """
        List all objects in a bucket.

        Args:
            bucket: Bucket name
            prefix: Key prefix filter
            max_keys: Maximum keys per request

        Yields:
            ObjectInfo for each object
        """
        paginator = self.client.get_paginator("list_objects_v2")
        pages = paginator.paginate(
            Bucket=bucket, Prefix=prefix, PaginationConfig={"PageSize": max_keys}
        )

        for page in pages:
            for obj in page.get("Contents", []):
                yield ObjectInfo(
                    key=obj["Key"],
                    size=obj["Size"],
                    etag=obj["ETag"].strip('"'),
                    last_modified=obj["LastModified"],
                )

    def get_object(self, bucket: str, key: str) -> Tuple[bytes, Dict[str, Any]]:
        """
        Get an object and its metadata.

        Args:
            bucket: Bucket name
            key: Object key

        Returns:
            Tuple of (object data, metadata dict)
        """
        response = self.client.get_object(Bucket=bucket, Key=key)
        data = response["Body"].read()
        metadata = {
            "ContentType": response.get("ContentType", "application/octet-stream"),
            "Metadata": response.get("Metadata", {}),
            "ETag": response.get("ETag", "").strip('"'),
        }
        return data, metadata

    def put_object(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Put an object into a bucket.

        Args:
            bucket: Bucket name
            key: Object key
            data: Object data
            content_type: Content type
            metadata: Optional metadata

        Returns:
            ETag of the uploaded object
        """
        kwargs = {
            "Bucket": bucket,
            "Key": key,
            "Body": data,
            "ContentType": content_type,
        }
        if metadata:
            kwargs["Metadata"] = metadata

        response = self.client.put_object(**kwargs)
        return response.get("ETag", "").strip('"')

    def delete_object(self, bucket: str, key: str) -> bool:
        """
        Delete an object.

        Args:
            bucket: Bucket name
            key: Object key

        Returns:
            True if deleted successfully
        """
        self.client.delete_object(Bucket=bucket, Key=key)
        return True

    def export_bucket(
        self,
        bucket: str,
        output_path: str,
        prefix: str = "",
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> BackupManifest:
        """
        Export all objects from a bucket to a tar.gz archive.

        Args:
            bucket: Bucket name to export
            output_path: Path for the output archive
            prefix: Optional key prefix filter
            progress_callback: Optional callback(current, total) for progress

        Returns:
            BackupManifest with export details
        """
        logger.info(f"Starting export of bucket '{bucket}' to '{output_path}'")

        # First, list all objects
        objects = list(self.list_objects(bucket, prefix=prefix))
        total_objects = len(objects)
        total_size = sum(obj.size for obj in objects)

        logger.info(f"Found {total_objects} objects ({total_size} bytes)")

        manifest_objects = []
        exported_count = 0

        with tarfile.open(output_path, "w:gz") as tar:
            for obj in objects:
                try:
                    # Get object data
                    data, metadata = self.get_object(bucket, obj.key)

                    # Add to tar
                    tarinfo = tarfile.TarInfo(name=obj.key)
                    tarinfo.size = len(data)
                    tarinfo.mtime = obj.last_modified.timestamp()
                    tar.addfile(tarinfo, io.BytesIO(data))

                    # Record in manifest
                    manifest_objects.append(
                        {
                            "key": obj.key,
                            "size": obj.size,
                            "etag": obj.etag,
                            "content_type": metadata.get("ContentType"),
                            "metadata": metadata.get("Metadata", {}),
                        }
                    )

                    exported_count += 1
                    if progress_callback:
                        progress_callback(exported_count, total_objects)

                    logger.debug(f"Exported: {obj.key}")

                except Exception as e:
                    logger.error(f"Failed to export {obj.key}: {e}")

            # Add manifest to archive
            manifest = BackupManifest(
                version="1.0",
                created_at=datetime.utcnow().isoformat(),
                bucket=bucket,
                total_objects=exported_count,
                total_size=total_size,
                objects=manifest_objects,
            )

            manifest_data = json.dumps(manifest.__dict__, indent=2).encode("utf-8")
            manifest_info = tarfile.TarInfo(name="_manifest.json")
            manifest_info.size = len(manifest_data)
            tar.addfile(manifest_info, io.BytesIO(manifest_data))

        logger.info(f"Export complete: {exported_count}/{total_objects} objects")
        return manifest

    def import_bucket(
        self,
        bucket: str,
        input_path: str,
        overwrite: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, Any]:
        """
        Import objects from a tar.gz archive into a bucket.

        Args:
            bucket: Bucket name to import into
            input_path: Path to the input archive
            overwrite: Whether to overwrite existing objects
            progress_callback: Optional callback(current, total) for progress

        Returns:
            Dictionary with import results
        """
        logger.info(f"Starting import to bucket '{bucket}' from '{input_path}'")

        results = {
            "imported": 0,
            "skipped": 0,
            "failed": 0,
            "errors": [],
        }

        manifest = None

        with tarfile.open(input_path, "r:gz") as tar:
            members = tar.getmembers()
            total = len(members)

            # Load manifest first if available
            try:
                manifest_file = tar.extractfile("_manifest.json")
                if manifest_file:
                    manifest = json.loads(manifest_file.read().decode("utf-8"))
            except (KeyError, Exception) as e:
                logger.warning(f"Could not load manifest: {e}")

            # Build metadata lookup from manifest
            metadata_lookup = {}
            if manifest and "objects" in manifest:
                for obj in manifest["objects"]:
                    metadata_lookup[obj["key"]] = obj

            processed = 0
            for member in members:
                if member.name == "_manifest.json":
                    continue

                try:
                    # Check if object exists
                    if not overwrite:
                        try:
                            self.client.head_object(Bucket=bucket, Key=member.name)
                            results["skipped"] += 1
                            continue
                        except Exception:
                            pass

                    # Extract and upload
                    file_obj = tar.extractfile(member)
                    if file_obj:
                        data = file_obj.read()

                        # Get metadata from manifest if available
                        obj_meta = metadata_lookup.get(member.name, {})
                        content_type = obj_meta.get(
                            "content_type", "application/octet-stream"
                        )
                        metadata = obj_meta.get("metadata", {})

                        self.put_object(
                            bucket,
                            member.name,
                            data,
                            content_type=content_type,
                            metadata=metadata,
                        )

                        results["imported"] += 1
                        logger.debug(f"Imported: {member.name}")

                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append({"key": member.name, "error": str(e)})
                    logger.error(f"Failed to import {member.name}: {e}")

                processed += 1
                if progress_callback:
                    progress_callback(processed, total)

        logger.info(
            f"Import complete: {results['imported']} imported, "
            f"{results['skipped']} skipped, {results['failed']} failed"
        )
        return results

    def sync_buckets(
        self,
        source_bucket: str,
        dest_bucket: str,
        prefix: str = "",
        delete_orphans: bool = False,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, Any]:
        """
        Sync objects from source bucket to destination bucket.

        Args:
            source_bucket: Source bucket name
            dest_bucket: Destination bucket name
            prefix: Optional key prefix filter
            delete_orphans: Delete objects in dest that don't exist in source
            progress_callback: Optional callback(current, total) for progress

        Returns:
            Dictionary with sync results
        """
        logger.info(f"Syncing from '{source_bucket}' to '{dest_bucket}'")

        results = {
            "copied": 0,
            "skipped": 0,
            "deleted": 0,
            "failed": 0,
        }

        # Get source and dest objects
        source_objects = {obj.key: obj for obj in self.list_objects(source_bucket, prefix)}
        dest_objects = {obj.key: obj for obj in self.list_objects(dest_bucket, prefix)}

        total = len(source_objects)
        processed = 0

        # Copy new or modified objects
        for key, src_obj in source_objects.items():
            try:
                dest_obj = dest_objects.get(key)

                # Skip if ETags match
                if dest_obj and dest_obj.etag == src_obj.etag:
                    results["skipped"] += 1
                else:
                    # Copy object
                    data, metadata = self.get_object(source_bucket, key)
                    self.put_object(
                        dest_bucket,
                        key,
                        data,
                        content_type=metadata.get("ContentType", "application/octet-stream"),
                        metadata=metadata.get("Metadata"),
                    )
                    results["copied"] += 1
                    logger.debug(f"Copied: {key}")

            except Exception as e:
                results["failed"] += 1
                logger.error(f"Failed to sync {key}: {e}")

            processed += 1
            if progress_callback:
                progress_callback(processed, total)

        # Delete orphans if requested
        if delete_orphans:
            for key in dest_objects:
                if key not in source_objects:
                    try:
                        self.delete_object(dest_bucket, key)
                        results["deleted"] += 1
                        logger.debug(f"Deleted orphan: {key}")
                    except Exception as e:
                        logger.error(f"Failed to delete {key}: {e}")

        logger.info(
            f"Sync complete: {results['copied']} copied, "
            f"{results['skipped']} skipped, {results['deleted']} deleted"
        )
        return results

    def export_to_directory(
        self,
        bucket: str,
        output_dir: str,
        prefix: str = "",
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, Any]:
        """
        Export all objects from a bucket to a local directory.

        Args:
            bucket: Bucket name to export
            output_dir: Output directory path
            prefix: Optional key prefix filter
            progress_callback: Optional callback(current, total) for progress

        Returns:
            Dictionary with export results
        """
        logger.info(f"Exporting bucket '{bucket}' to directory '{output_dir}'")

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        results = {"exported": 0, "failed": 0, "total_size": 0}

        objects = list(self.list_objects(bucket, prefix=prefix))
        total = len(objects)

        for i, obj in enumerate(objects):
            try:
                data, metadata = self.get_object(bucket, obj.key)

                # Create subdirectories if needed
                file_path = output_path / obj.key
                file_path.parent.mkdir(parents=True, exist_ok=True)

                # Write file
                file_path.write_bytes(data)

                results["exported"] += 1
                results["total_size"] += len(data)

            except Exception as e:
                results["failed"] += 1
                logger.error(f"Failed to export {obj.key}: {e}")

            if progress_callback:
                progress_callback(i + 1, total)

        # Write manifest
        manifest_path = output_path / "_manifest.json"
        manifest = {
            "version": "1.0",
            "created_at": datetime.utcnow().isoformat(),
            "bucket": bucket,
            "total_objects": results["exported"],
            "total_size": results["total_size"],
        }
        manifest_path.write_text(json.dumps(manifest, indent=2))

        logger.info(f"Export complete: {results['exported']} objects")
        return results

    def import_from_directory(
        self,
        bucket: str,
        input_dir: str,
        prefix: str = "",
        overwrite: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, Any]:
        """
        Import objects from a local directory into a bucket.

        Args:
            bucket: Bucket name to import into
            input_dir: Input directory path
            prefix: Optional key prefix to add
            overwrite: Whether to overwrite existing objects
            progress_callback: Optional callback(current, total) for progress

        Returns:
            Dictionary with import results
        """
        logger.info(f"Importing from directory '{input_dir}' to bucket '{bucket}'")

        input_path = Path(input_dir)
        results = {"imported": 0, "skipped": 0, "failed": 0}

        # Get all files
        files = [f for f in input_path.rglob("*") if f.is_file() and f.name != "_manifest.json"]
        total = len(files)

        for i, file_path in enumerate(files):
            try:
                # Calculate key
                relative_path = file_path.relative_to(input_path)
                key = prefix + str(relative_path)

                # Check if exists
                if not overwrite:
                    try:
                        self.client.head_object(Bucket=bucket, Key=key)
                        results["skipped"] += 1
                        continue
                    except Exception:
                        pass

                # Upload
                data = file_path.read_bytes()
                self.put_object(bucket, key, data)
                results["imported"] += 1

            except Exception as e:
                results["failed"] += 1
                logger.error(f"Failed to import {file_path}: {e}")

            if progress_callback:
                progress_callback(i + 1, total)

        logger.info(f"Import complete: {results['imported']} objects")
        return results
