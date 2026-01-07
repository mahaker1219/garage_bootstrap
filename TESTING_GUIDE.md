# Testing Guide for Garage Bootstrap

This guide explains how to run tests against a live Garage cluster to validate connectivity and functionality.

## Prerequisites

1. **Running Garage Cluster**: You need a Garage cluster accessible from your machine
2. **Python 3.8+**: With pip installed
3. **Admin Access**: Admin token for the Garage cluster (for bootstrap tests)
4. **S3 Credentials**: Access key and secret key with bucket permissions (for connectivity tests)

## Quick Start

### 1. Install Dependencies

```bash
cd garage_bootstrap
pip install -r requirements.txt
```

### 2. Set Environment Variables

```bash
# Garage Admin API (port 3903)
export GARAGE_ADMIN_ENDPOINT="http://your-garage-host:3903"
export GARAGE_ADMIN_TOKEN="your-admin-token"

# Garage S3 API (port 3900)
export GARAGE_S3_ENDPOINT="your-garage-host:3900"

# Test credentials (access key created in Garage)
export TEST_ACCESS_KEY="GKxxxxxxxxxxxxxxxxxx"
export TEST_SECRET_KEY="your-secret-key"
export TEST_BUCKET="your-test-bucket"
export TEST_REGION="garage"
export TEST_SECURE="false"  # Set to "true" for HTTPS
```

### 3. Run Tests

```bash
# Run all unit tests (mocked, no live cluster needed)
make test-unit

# Run integration tests (requires live Garage cluster)
make test-integration

# Run connectivity tests only
python -m garage_bootstrap.scripts.test_connectivity

# Run specific library test
python -m garage_bootstrap.scripts.test_connectivity --library minio
python -m garage_bootstrap.scripts.test_connectivity --library s3
python -m garage_bootstrap.scripts.test_connectivity --library azure
```

## Test Types

### Unit Tests (Mocked)
These tests use mocked clients and don't require a live cluster:
```bash
pytest tests/ -v -m "not integration and not persistence"
```

### Integration Tests
These tests require a live Garage cluster:
```bash
pytest tests/ -v -m "integration"
```

### Persistence Tests
Multi-stage tests that verify data survives pod restarts:
```bash
# Stage 1: Create test data
pytest tests/test_persistence.py -v -m "stage1"

# (Restart your Garage pods here)

# Stage 2: Verify data persisted
pytest tests/test_persistence.py -v -m "stage2"
```

## CLI Tools for Live Testing

### Connectivity Test CLI

Test S3 connectivity against your live cluster:

```bash
# Using environment variables
python -m garage_bootstrap.scripts.test_connectivity

# Using command-line arguments
python -m garage_bootstrap.scripts.test_connectivity \
    --endpoint "your-garage-host:3900" \
    --access-key "GKxxxxxxxxxxxxxxxxxx" \
    --secret-key "your-secret-key" \
    --bucket "test-bucket" \
    --region "garage"

# Test specific library
python -m garage_bootstrap.scripts.test_connectivity --library minio
python -m garage_bootstrap.scripts.test_connectivity --library s3

# With verbose output
python -m garage_bootstrap.scripts.test_connectivity -v

# JSON output for scripting
python -m garage_bootstrap.scripts.test_connectivity --output json
```

### Bootstrap Test CLI

Test the bootstrap process against your cluster:

```bash
# Dry run (shows what would be created)
python -m garage_bootstrap.scripts.bootstrap \
    --endpoint "http://your-garage-host:3903" \
    --token "your-admin-token" \
    --config path/to/config.yaml \
    --dry-run

# Actual bootstrap
python -m garage_bootstrap.scripts.bootstrap \
    --endpoint "http://your-garage-host:3903" \
    --token "your-admin-token" \
    --config path/to/config.yaml
```

## Environment Variable Reference

| Variable | Description | Default | Required For |
|----------|-------------|---------|--------------|
| `GARAGE_ADMIN_ENDPOINT` | Admin API URL (port 3903) | `http://localhost:3903` | Bootstrap tests |
| `GARAGE_ADMIN_TOKEN` | Admin authentication token | - | Bootstrap tests |
| `GARAGE_S3_ENDPOINT` | S3 API endpoint (port 3900) | `localhost:3900` | Connectivity tests |
| `TEST_ACCESS_KEY` | S3 access key ID | `GKtest123` | Connectivity tests |
| `TEST_SECRET_KEY` | S3 secret access key | `testsecret123` | Connectivity tests |
| `TEST_BUCKET` | Bucket name for testing | `test-bucket` | Connectivity tests |
| `TEST_REGION` | S3 region name | `garage` | Connectivity tests |
| `TEST_SECURE` | Use HTTPS (`true`/`false`) | `false` | All tests |

## Sample Configuration Files

### Bootstrap Configuration (YAML)

```yaml
# config/bootstrap.yaml
buckets:
  - name: app-data
    keys:
      - app-key
    permissions:
      app-key:
        read: true
        write: true
        owner: false
  - name: backups
    quotas:
      maxSize: 10737418240  # 10GB

keys:
  - name: app-key
    allowCreateBucket: false
  - name: admin-key
    allowCreateBucket: true
```

### Bootstrap Configuration (JSON)

```json
{
  "buckets": [
    {
      "name": "app-data",
      "keys": ["app-key"],
      "permissions": {
        "app-key": {"read": true, "write": true, "owner": false}
      }
    }
  ],
  "keys": [
    {"name": "app-key", "allowCreateBucket": false}
  ]
}
```

## Running Tests in Docker

```bash
# Build the test image
docker build -t garage-bootstrap:test -f garage_bootstrap/Dockerfile garage_bootstrap

# Run tests with environment variables
docker run --rm \
    -e GARAGE_S3_ENDPOINT="your-garage-host:3900" \
    -e TEST_ACCESS_KEY="GKxxxxxxxxxxxxxxxxxx" \
    -e TEST_SECRET_KEY="your-secret-key" \
    -e TEST_BUCKET="test-bucket" \
    garage-bootstrap:test \
    python -m garage_bootstrap.scripts.test_connectivity
```

## Running Tests in Kubernetes

```bash
# Create a test pod
kubectl run garage-test --rm -it \
    --image=garage-bootstrap:latest \
    --env="GARAGE_S3_ENDPOINT=garage:3900" \
    --env="TEST_ACCESS_KEY=GKxxxxxxxxxxxxxxxxxx" \
    --env="TEST_SECRET_KEY=your-secret-key" \
    --env="TEST_BUCKET=test-bucket" \
    -- python -m garage_bootstrap.scripts.test_connectivity
```

## Troubleshooting

### Connection Refused
- Verify Garage is running and accessible
- Check firewall rules allow access to ports 3900 (S3) and 3903 (Admin)
- For Kubernetes, ensure you're using the correct service name

### Access Denied
- Verify access key and secret key are correct
- Ensure the key has permissions on the test bucket
- Check if the bucket exists

### Bucket Not Found
- Create the test bucket first using the admin API or CLI
- Verify the bucket name is correct

### SSL/TLS Errors
- Set `TEST_SECURE=false` for HTTP endpoints
- For HTTPS, ensure certificates are valid or add `--insecure` flag

## Example: Complete Test Workflow

```bash
# 1. Set up environment
export GARAGE_ADMIN_ENDPOINT="http://192.168.1.100:3903"
export GARAGE_ADMIN_TOKEN="s3cr3t-admin-token"
export GARAGE_S3_ENDPOINT="192.168.1.100:3900"

# 2. Create a test bucket and key using bootstrap
python -m garage_bootstrap.scripts.bootstrap \
    --endpoint "$GARAGE_ADMIN_ENDPOINT" \
    --token "$GARAGE_ADMIN_TOKEN" \
    --config - <<EOF
buckets:
  - name: integration-test
    keys:
      - test-key
keys:
  - name: test-key
EOF

# 3. Get the created credentials (from bootstrap output)
export TEST_ACCESS_KEY="GK..."  # From output
export TEST_SECRET_KEY="..."     # From output
export TEST_BUCKET="integration-test"

# 4. Run connectivity tests
python -m garage_bootstrap.scripts.test_connectivity -v

# 5. Run full integration test suite
pytest tests/ -v -m "integration"

# 6. Clean up (optional)
# Delete test bucket and key via admin API
```

## CI/CD Integration

### GitHub Actions Example

```yaml
jobs:
  integration-test:
    runs-on: ubuntu-latest
    services:
      garage:
        image: dxflrs/garage:v1.0.0
        ports:
          - 3900:3900
          - 3903:3903
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r garage_bootstrap/requirements.txt
      - run: |
          export GARAGE_S3_ENDPOINT="localhost:3900"
          export GARAGE_ADMIN_ENDPOINT="http://localhost:3903"
          # ... set up keys and run tests
          pytest garage_bootstrap/tests/ -v -m "integration"
```
