# Makefile for Garage Bootstrap
#
# Usage:
#   make build                    # Build Docker image with default tag
#   make build IMG_TAG=v1.0.0     # Build with specific tag
#   make push REGISTRY=myregistry.io IMG_TAG=v1.0.0   # Push to registry
#   make test                     # Run tests
#   make lint                     # Run linters

# Default values
REGISTRY ?= ghcr.io/mahaker1219
IMAGE_NAME ?= garage-bootstrap
IMG_TAG ?= latest
FULL_IMAGE = $(REGISTRY)/$(IMAGE_NAME):$(IMG_TAG)

# Python settings
PYTHON ?= python3
PIP ?= pip3
PYTEST ?= pytest

# Directories
CHART_DIR = chart
SRC_DIR = garage_bootstrap
SCRIPTS_DIR = scripts

.PHONY: all build push test lint clean help version update-version

# Default target
all: lint test build

##@ General

help: ## Display this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_0-9-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Development

install: ## Install development dependencies
	$(PIP) install -r $(SRC_DIR)/requirements.txt
	$(PIP) install black flake8 mypy

lint: ## Run linters
	@echo "Running flake8..."
	-flake8 $(SRC_DIR) --max-line-length=100 --ignore=E501,W503
	@echo "Linting complete"

format: ## Format code with black
	black $(SRC_DIR) $(SCRIPTS_DIR)

type-check: ## Run mypy type checking
	mypy $(SRC_DIR) --ignore-missing-imports

##@ Testing

test: ## Run all tests
	cd $(SRC_DIR) && $(PYTEST) tests/ -v

test-unit: ## Run unit tests only
	cd $(SRC_DIR) && $(PYTEST) tests/ -v -m "not integration and not persistence"

test-integration: ## Run integration tests (requires running Garage)
	cd $(SRC_DIR) && $(PYTEST) tests/ -v -m "integration"

test-connectivity: ## Run connectivity tests against live cluster (set TEST_* env vars)
	$(PYTHON) -m garage_bootstrap.scripts.test_connectivity

test-connectivity-minio: ## Run MinIO connectivity test
	$(PYTHON) -m garage_bootstrap.scripts.test_connectivity --library minio

test-connectivity-s3: ## Run S3 (boto3) connectivity test
	$(PYTHON) -m garage_bootstrap.scripts.test_connectivity --library s3

test-connectivity-azure: ## Run Azure Blob connectivity test
	$(PYTHON) -m garage_bootstrap.scripts.test_connectivity --library azure

test-persistence-stage1: ## Run persistence test stage 1
	cd $(SRC_DIR) && $(PYTEST) tests/test_persistence.py -v -m "stage1"

test-persistence-stage2: ## Run persistence test stage 2 (after Garage restart)
	cd $(SRC_DIR) && $(PYTEST) tests/test_persistence.py -v -m "stage2"

test-coverage: ## Run tests with coverage
	cd $(SRC_DIR) && $(PYTEST) tests/ -v --cov=. --cov-report=html --cov-report=term

##@ Docker

build: ## Build Docker image
	@echo "Building Docker image: $(FULL_IMAGE)"
	docker build -t $(FULL_IMAGE) -f $(SRC_DIR)/Dockerfile $(SRC_DIR)
	@echo "Built: $(FULL_IMAGE)"

build-no-cache: ## Build Docker image without cache
	docker build --no-cache -t $(FULL_IMAGE) -f $(SRC_DIR)/Dockerfile $(SRC_DIR)

push: ## Push Docker image to registry
	@echo "Pushing image: $(FULL_IMAGE)"
	docker push $(FULL_IMAGE)
	@echo "Pushed: $(FULL_IMAGE)"

build-push: build push ## Build and push Docker image

docker-run: ## Run Docker container locally
	docker run --rm -it $(FULL_IMAGE)

docker-shell: ## Run Docker container with shell
	docker run --rm -it --entrypoint /bin/bash $(FULL_IMAGE)

##@ Versioning

version: ## Show current version
	@grep -E "^__version__|^version:|^appVersion:" $(SRC_DIR)/__init__.py $(CHART_DIR)/Chart.yaml 2>/dev/null || echo "Version files not found"

update-version: ## Update version across all files (usage: make update-version IMG_TAG=v1.0.0)
	@if [ "$(IMG_TAG)" = "latest" ]; then \
		echo "Error: Please specify IMG_TAG (e.g., make update-version IMG_TAG=v1.0.0)"; \
		exit 1; \
	fi
	$(PYTHON) $(SCRIPTS_DIR)/update_version.py --version $(IMG_TAG)

##@ Helm

helm-lint: ## Lint Helm chart
	helm lint $(CHART_DIR)

helm-template: ## Render Helm templates
	helm template garage-bootstrap $(CHART_DIR)

helm-package: ## Package Helm chart
	helm package $(CHART_DIR)

helm-install: ## Install Helm chart (dry-run)
	helm install garage-bootstrap $(CHART_DIR) --dry-run --debug

##@ Clean

clean: ## Clean build artifacts
	rm -rf $(SRC_DIR)/__pycache__
	rm -rf $(SRC_DIR)/tests/__pycache__
	rm -rf $(SRC_DIR)/.pytest_cache
	rm -rf $(SRC_DIR)/htmlcov
	rm -rf $(SRC_DIR)/.coverage
	rm -rf *.tgz
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

clean-docker: ## Remove Docker images
	-docker rmi $(FULL_IMAGE)

clean-all: clean clean-docker ## Clean everything

##@ CI/CD

ci-test: install test lint ## Run CI test pipeline

ci-build: ## CI build pipeline
	$(MAKE) build IMG_TAG=$(IMG_TAG)
	$(MAKE) helm-lint

ci-release: ## CI release pipeline (build, test, push)
	$(MAKE) update-version IMG_TAG=$(IMG_TAG)
	$(MAKE) test
	$(MAKE) build IMG_TAG=$(IMG_TAG)
	$(MAKE) push REGISTRY=$(REGISTRY) IMG_TAG=$(IMG_TAG)
