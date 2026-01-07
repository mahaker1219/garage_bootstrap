# Makefile for Garage Bootstrap and Garage Test
#
# Usage:
#   make build                    # Build both Docker images
#   make build-bootstrap          # Build bootstrap image only
#   make build-test               # Build test image only
#   make push REGISTRY=myregistry.io IMG_TAG=v1.0.0   # Push to registry
#   make test                     # Run all tests
#   make lint                     # Run linters

# Default values
REGISTRY ?= ghcr.io/mahaker1219
IMG_TAG ?= latest

# Image names
BOOTSTRAP_IMAGE_NAME ?= garage-bootstrap
TEST_IMAGE_NAME ?= garage-test
BOOTSTRAP_IMAGE = $(REGISTRY)/$(BOOTSTRAP_IMAGE_NAME):$(IMG_TAG)
TEST_IMAGE = $(REGISTRY)/$(TEST_IMAGE_NAME):$(IMG_TAG)

# Python settings
PYTHON ?= python3
PIP ?= pip3
PYTEST ?= pytest

# Directories
CHART_DIR = chart
BOOTSTRAP_DIR = garage_bootstrap
TEST_DIR = garage_test
SCRIPTS_DIR = scripts

.PHONY: all build push test lint clean help version update-version

# Default target
all: lint test build

##@ General

help: ## Display this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_0-9-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Development

install: ## Install all dependencies
	$(PIP) install -r $(BOOTSTRAP_DIR)/requirements.txt
	$(PIP) install -r $(TEST_DIR)/requirements.txt

install-bootstrap: ## Install bootstrap dependencies only
	$(PIP) install -r $(BOOTSTRAP_DIR)/requirements.txt

install-test: ## Install test dependencies only
	$(PIP) install -r $(TEST_DIR)/requirements.txt

lint: ## Run linters on all code
	@echo "Running flake8..."
	-flake8 $(BOOTSTRAP_DIR) $(TEST_DIR) --max-line-length=100 --ignore=E501,W503
	@echo "Linting complete"

format: ## Format code with black
	black $(BOOTSTRAP_DIR) $(TEST_DIR) $(SCRIPTS_DIR)

##@ Testing - Bootstrap

test-bootstrap: ## Run bootstrap unit tests
	cd $(BOOTSTRAP_DIR) && $(PYTEST) tests/ -v

##@ Testing - Connectivity & Integration

test-all: ## Run all tests (bootstrap + test)
	cd $(BOOTSTRAP_DIR) && $(PYTEST) tests/ -v
	cd $(TEST_DIR) && $(PYTEST) tests/ -v -m "not integration and not persistence"

test-unit: ## Run unit tests only (no live cluster needed)
	cd $(TEST_DIR) && $(PYTEST) tests/ -v -m "not integration and not persistence"

test-integration: ## Run integration tests (requires running Garage)
	cd $(TEST_DIR) && $(PYTEST) tests/ -v -m "integration"

test-connectivity: ## Run connectivity tests against live cluster (set TEST_* env vars)
	$(PYTHON) -m garage_test.scripts.test_connectivity

test-connectivity-minio: ## Run MinIO connectivity test
	$(PYTHON) -m garage_test.scripts.test_connectivity --library minio

test-connectivity-s3: ## Run S3 (boto3) connectivity test
	$(PYTHON) -m garage_test.scripts.test_connectivity --library s3

test-connectivity-azure: ## Run Azure Blob connectivity test
	$(PYTHON) -m garage_test.scripts.test_connectivity --library azure

test-persistence-stage1: ## Run persistence test stage 1
	cd $(TEST_DIR) && $(PYTEST) tests/test_persistence.py -v -m "stage1"

test-persistence-stage2: ## Run persistence test stage 2 (after Garage restart)
	cd $(TEST_DIR) && $(PYTEST) tests/test_persistence.py -v -m "stage2"

test-coverage: ## Run tests with coverage
	cd $(TEST_DIR) && $(PYTEST) tests/ -v --cov=. --cov-report=html --cov-report=term

##@ Docker - Bootstrap

build-bootstrap: ## Build bootstrap Docker image
	@echo "Building Docker image: $(BOOTSTRAP_IMAGE)"
	docker build -t $(BOOTSTRAP_IMAGE) -f $(BOOTSTRAP_DIR)/Dockerfile $(BOOTSTRAP_DIR)
	@echo "Built: $(BOOTSTRAP_IMAGE)"

push-bootstrap: ## Push bootstrap Docker image
	@echo "Pushing image: $(BOOTSTRAP_IMAGE)"
	docker push $(BOOTSTRAP_IMAGE)
	@echo "Pushed: $(BOOTSTRAP_IMAGE)"

##@ Docker - Test

build-test: ## Build test Docker image
	@echo "Building Docker image: $(TEST_IMAGE)"
	docker build -t $(TEST_IMAGE) -f $(TEST_DIR)/Dockerfile $(TEST_DIR)
	@echo "Built: $(TEST_IMAGE)"

push-test: ## Push test Docker image
	@echo "Pushing image: $(TEST_IMAGE)"
	docker push $(TEST_IMAGE)
	@echo "Pushed: $(TEST_IMAGE)"

##@ Docker - Both

build: build-bootstrap build-test ## Build both Docker images

push: push-bootstrap push-test ## Push both Docker images

build-push: build push ## Build and push both images

docker-run-bootstrap: ## Run bootstrap container locally
	docker run --rm -it $(BOOTSTRAP_IMAGE)

docker-run-test: ## Run test container locally
	docker run --rm -it $(TEST_IMAGE)

docker-shell-bootstrap: ## Run bootstrap container with shell
	docker run --rm -it --entrypoint /bin/bash $(BOOTSTRAP_IMAGE)

docker-shell-test: ## Run test container with shell
	docker run --rm -it --entrypoint /bin/bash $(TEST_IMAGE)

##@ Versioning

version: ## Show current version
	@echo "Bootstrap version:"
	@grep -E "^__version__" $(BOOTSTRAP_DIR)/__init__.py 2>/dev/null || echo "  Not found"
	@echo "Test version:"
	@grep -E "^__version__" $(TEST_DIR)/__init__.py 2>/dev/null || echo "  Not found"
	@echo "Chart version:"
	@grep -E "^version:|^appVersion:" $(CHART_DIR)/Chart.yaml 2>/dev/null || echo "  Not found"

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
	rm -rf $(BOOTSTRAP_DIR)/__pycache__
	rm -rf $(BOOTSTRAP_DIR)/tests/__pycache__
	rm -rf $(BOOTSTRAP_DIR)/.pytest_cache
	rm -rf $(TEST_DIR)/__pycache__
	rm -rf $(TEST_DIR)/tests/__pycache__
	rm -rf $(TEST_DIR)/.pytest_cache
	rm -rf $(TEST_DIR)/htmlcov
	rm -rf $(TEST_DIR)/.coverage
	rm -rf *.tgz
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

clean-docker: ## Remove Docker images
	-docker rmi $(BOOTSTRAP_IMAGE)
	-docker rmi $(TEST_IMAGE)

clean-all: clean clean-docker ## Clean everything

##@ CI/CD

ci-test: install test-all lint ## Run CI test pipeline

ci-build: ## CI build pipeline
	$(MAKE) build IMG_TAG=$(IMG_TAG)
	$(MAKE) helm-lint

ci-release: ## CI release pipeline (build, test, push)
	$(MAKE) update-version IMG_TAG=$(IMG_TAG)
	$(MAKE) test-all
	$(MAKE) build IMG_TAG=$(IMG_TAG)
	$(MAKE) push REGISTRY=$(REGISTRY) IMG_TAG=$(IMG_TAG)
