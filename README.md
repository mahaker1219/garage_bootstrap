# Garage Bootstrap

A helper service and Helm chart for declaratively bootstrapping [Garage](https://garagehq.deuxfleurs.fr/) S3-compatible object storage clusters.

## Overview

Garage is an S3-compatible distributed object storage system designed for self-hosting. This project provides two services:

### garage_bootstrap/
- **Bootstrap Service**: A Docker container for cluster initialization
- **Helm Chart Integration**: Declarative bucket and access key creation via GitOps

### garage_test/
- **Connectivity Tests**: Validation scripts using MinIO, boto3 (S3), and Azure Blob Storage clients
- **Data Management**: Backup and restore utilities for application-level data persistence
- **Persistence Tests**: Multi-stage tests for data persistence across pod restarts

### Why Garage?

| Pros | Cons (Addressed by this project) |
|------|----------------------------------|
| More latency resistant than MinIO (write now, reconcile later) | Default container is minimal (no bash, curl, etc.) |
| Free and open source | No built-in declarative bootstrapping |
| Less complexity than Rook-based provisioning | Requires manual bucket/key creation |

This project addresses the cons by providing a feature-rich bootstrap container and Helm chart for GitOps workflows.

## Quick Start

### Prerequisites

- Docker
- Kubernetes cluster with Helm 3
- Running Garage cluster

### Installation

1. **Build the Docker images:**

```bash
# Build both images
make build IMG_TAG=v0.1.0

# Or build individually
make build-bootstrap IMG_TAG=v0.1.0
make build-test IMG_TAG=v0.1.0
```

2. **Install the Helm chart:**

```bash
helm install garage-bootstrap ./chart \
  --set garage.adminEndpoint=http://garage:3903 \
  --set garage.adminToken=your-admin-token \
  --set buckets[0].name=my-bucket \
  --set keys[0].name=my-key
```

## Features

### Declarative Bucket Creation

Define buckets and access keys in your Helm values:

```yaml
buckets:
  - name: app-data
    keys:
      - app-key
    permissions:
      app-key:
        read: true
        write: true
        owner: false
    quotas:
      maxSize: 10737418240  # 10GB

keys:
  - name: app-key
    allowCreateBucket: false
  - name: admin-key
    allowCreateBucket: true
```

### Connectivity Testing

Test S3 compatibility with multiple client libraries:

```bash
# Run all connectivity tests
cd garage_bootstrap
pytest tests/test_connectivity.py -v

# Test with specific library
pytest tests/test_connectivity.py::TestMinioConnectivity -v
pytest tests/test_connectivity.py::TestS3Connectivity -v
pytest tests/test_connectivity.py::TestAzureBlobConnectivity -v
```

### Data Backup/Export

Export bucket data for backup:

```python
from garage_bootstrap.data_manager import DataManager

manager = DataManager(
    endpoint="localhost:3900",
    access_key="your-key",
    secret_key="your-secret",
)

# Export to tar.gz archive
manager.export_bucket("my-bucket", "/backups/my-bucket.tar.gz")

# Export to directory
manager.export_to_directory("my-bucket", "/backups/my-bucket/")
```

### Data Import/Restore

```python
# Import from archive
manager.import_bucket("my-bucket", "/backups/my-bucket.tar.gz")

# Import from directory
manager.import_from_directory("my-bucket", "/backups/my-bucket/")
```

### Multi-Stage Persistence Testing

Test data persistence across Garage pod restarts:

```bash
# Stage 1: Create test data
cd garage_test && pytest tests/test_persistence.py -v -m "stage1"

# Restart Garage pods here...

# Stage 2: Verify data persisted
cd garage_test && pytest tests/test_persistence.py -v -m "stage2"
```

## Project Structure

```
garage_bootstrap/
├── garage_bootstrap/          # Bootstrap service (for Helm chart)
│   ├── __init__.py
│   ├── admin_client.py       # Garage Admin API client
│   ├── bootstrap.py          # Bootstrap logic
│   ├── Dockerfile            # Container image
│   ├── requirements.txt      # Python dependencies
│   ├── scripts/
│   │   └── bootstrap.py      # CLI entry point
│   └── tests/
│       ├── conftest.py       # Test fixtures
│       ├── test_admin_client.py
│       └── test_bootstrap.py
├── garage_test/               # Testing service
│   ├── __init__.py
│   ├── connectivity.py       # S3 connectivity tests
│   ├── data_manager.py       # Backup/restore utilities
│   ├── Dockerfile            # Container image
│   ├── requirements.txt      # Python dependencies
│   ├── pytest.ini            # Pytest configuration
│   ├── scripts/
│   │   └── test_connectivity.py  # CLI for connectivity tests
│   └── tests/
│       ├── conftest.py       # Test fixtures
│       ├── test_connectivity.py
│       ├── test_data_manager.py
│       ├── test_integration.py
│       └── test_persistence.py
├── chart/                     # Helm chart
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│       ├── _helpers.tpl
│       ├── bootstrap-job.yaml
│       ├── configmap.yaml
│       ├── connectivity-test-job.yaml
│       ├── secret-admin-token.yaml
│       ├── serviceaccount.yaml
│       └── NOTES.txt
├── scripts/
│   └── update_version.py     # Version sync script
├── garage/                    # Garage source (submodule)
├── Makefile                   # Build automation
├── CLAUDE.md                  # Project requirements
└── README.md
```

## Makefile Commands

```bash
# Build Docker image
make build                          # Build with default tag
make build IMG_TAG=v1.0.0          # Build with specific tag
make build REGISTRY=myregistry.io  # Build with custom registry

# Push to registry
make push REGISTRY=myregistry.io IMG_TAG=v1.0.0

# Build and push
make build-push REGISTRY=myregistry.io IMG_TAG=v1.0.0

# Run tests
make test                           # All tests
make test-unit                      # Unit tests only
make test-integration               # Integration tests
make test-coverage                  # With coverage report

# Persistence tests
make test-persistence-stage1        # Stage 1: Create data
make test-persistence-stage2        # Stage 2: Verify after restart

# Version management
make version                        # Show current versions
make update-version IMG_TAG=v1.0.0  # Sync all version files

# Helm
make helm-lint                      # Lint chart
make helm-template                  # Render templates
make helm-package                   # Package chart

# Development
make install                        # Install dependencies
make lint                           # Run linters
make format                         # Format code
make clean                          # Clean build artifacts
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GARAGE_ADMIN_ENDPOINT` | Garage admin API URL | `http://localhost:3903` |
| `GARAGE_ADMIN_TOKEN` | Admin authentication token | Required |
| `GARAGE_S3_ENDPOINT` | S3 API endpoint for tests | `http://localhost:3900` |
| `GARAGE_BUCKETS` | Comma-separated bucket names | - |
| `GARAGE_KEYS` | Comma-separated key names | - |
| `GARAGE_BOOTSTRAP_CONFIG` | Full JSON configuration | - |

### Helm Values

See `chart/values.yaml` for all available options. Key configurations:

```yaml
garage:
  adminEndpoint: "http://garage:3903"
  s3Endpoint: "http://garage:3900"
  adminToken: "your-token"
  # Or use existing secret
  existingSecret:
    enabled: true
    name: garage-admin-secret
    key: admin-token

bootstrap:
  enabled: true
  image:
    repository: ghcr.io/mahaker1219/garage-bootstrap
    tag: "0.1.0"

buckets:
  - name: my-bucket
    keys: [my-key]

keys:
  - name: my-key
```

## API Reference

### GarageAdminClient

```python
from garage_bootstrap.admin_client import GarageAdminClient

client = GarageAdminClient(
    admin_endpoint="http://localhost:3903",
    admin_token="your-token",
)

# Cluster operations
client.health_check()
client.get_cluster_status()
client.get_layout()

# Bucket operations
client.list_buckets()
client.create_bucket(global_alias="my-bucket")
client.get_bucket("bucket-id")
client.delete_bucket("bucket-id")

# Key operations
client.list_keys()
client.create_key(name="my-key")
client.get_key("key-id")
client.delete_key("key-id")

# Permissions
client.allow_key_on_bucket(
    bucket_id="bucket-id",
    access_key_id="key-id",
    read=True,
    write=True,
    owner=False,
)
```

### GarageBootstrap

```python
from garage_bootstrap.bootstrap import GarageBootstrap, ClusterConfig, BucketConfig, KeyConfig

bootstrap = GarageBootstrap(client)

config = ClusterConfig(
    buckets=[BucketConfig(name="my-bucket", keys=["my-key"])],
    keys=[KeyConfig(name="my-key")],
)

result = bootstrap.bootstrap(config)
```

## Development

### Setup

```bash
# Clone repository
git clone https://github.com/mahaker1219/garage_bootstrap.git
cd garage_bootstrap

# Initialize submodules
git submodule update --init --recursive

# Install dependencies
make install

# Run tests
make test-all
```

### Building

```bash
# Build both Docker images
make build IMG_TAG=dev

# Build individually
make build-bootstrap IMG_TAG=dev
make build-test IMG_TAG=dev

# Test locally
docker run --rm garage-bootstrap:dev --help
docker run --rm garage-test:dev --help
```

## Testing Against a Live Cluster

For detailed instructions on running tests against a live Garage cluster, see **[TESTING_GUIDE.md](TESTING_GUIDE.md)**.

### Quick Test Commands

```bash
# Set up your environment
export GARAGE_S3_ENDPOINT="your-garage-host:3900"
export TEST_ACCESS_KEY="GKxxxxxxxxxxxxxxxxxx"
export TEST_SECRET_KEY="your-secret-key"
export TEST_BUCKET="test-bucket"

# Run connectivity tests
make test-connectivity

# Run specific library tests
make test-connectivity-minio
make test-connectivity-s3

# Run full integration test suite
make test-integration
```

## License

This project is open source. See the LICENSE file for details.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## References

- [Garage Documentation](https://garagehq.deuxfleurs.fr/documentation/)
- [Garage Admin API](https://garagehq.deuxfleurs.fr/documentation/reference-manual/admin-api/)
- [Garage GitHub](https://git.deuxfleurs.fr/Deuxfleurs/garage)