.PHONY: help build publish clean

# Detect platform: linux, darwin, or windows
UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Linux)
    PLATFORM := linux
else ifeq ($(UNAME_S),Darwin)
    PLATFORM := darwin
else
    PLATFORM := windows
endif

# Detect architecture: arm64 or amd64
UNAME_M := $(shell uname -m)
ifeq ($(UNAME_M),arm64)
    ARCH := arm64
else ifeq ($(UNAME_M),aarch64)
    ARCH := arm64
else
    ARCH := amd64
endif

# macOS sed -i requires a backup extension; Linux does not
ifeq ($(UNAME_S),Darwin)
    SED_INPLACE := sed -i ''
else
    SED_INPLACE := sed -i
endif

# Read version from installed smartloop package
VERSION := $(shell python3 -c "from smartloop import __version__; print(__version__)")

GCS_BUCKET := gs://smartloop-gcp-us-east-releases
BASE_URL := https://storage.googleapis.com/smartloop-gcp-us-east-releases/$(VERSION)
INSTALL_SCRIPT := install.sh
# Directory where PyInstaller outputs the built binary
DIST_DIR := dist/slp
ARCHIVE_NAME := slp.tar.gz
GCS_PATH := $(GCS_BUCKET)/$(VERSION)/$(PLATFORM)/$(ARCH)/$(ARCHIVE_NAME)

help:
	@echo "Available targets:"
	@echo "  build                - Build slp binary for current platform using PyInstaller"
	@echo "  publish              - Build, validate, and upload to GCS bucket ($(VERSION)/$(PLATFORM)/$(ARCH)/$(ARCHIVE_NAME))"
	@echo "  clean                - Clean all build artifacts"
	@echo "  update               - Update shasums for all platforms (darwin-arm64 + linux-amd64)"
	@echo "  update-darwin-arm64  - Download darwin/arm64 archive and update shasum in install.sh"
	@echo "  update-linux-amd64   - Download linux/amd64 archive and update shasum in install.sh"
	@echo "  update-version       - Update VERSION in install.sh to $(VERSION)"

build:
	@echo "Building slp for $(PLATFORM)/$(ARCH) (v$(VERSION))..."
	pyinstaller -y smartloop.spec
ifeq ($(UNAME_S),Darwin)
	@echo "Codesigning binaries for macOS (hardened runtime)..."
	@find dist/slp -name "*.so" -o -name "*.dylib" | xargs -I {} codesign --force --options runtime --entitlements packaging/macos/entitlements.mac.plist --sign - {}
	@codesign --force --options runtime --entitlements packaging/macos/entitlements.mac.plist --sign - dist/slp/slp
endif
	@echo "Verifying binary..."
	@$(DIST_DIR)/slp --help > /dev/null 2>&1 || (echo "ERROR: slp binary verification failed" && exit 1)
	@echo "Binary verified successfully."
	@echo "Compiling .pyc files for faster startup..."
	@python -m compileall -q -b $(DIST_DIR)
	@echo "Packaging $(ARCHIVE_NAME)..."
	@cd dist && tar czf ../$(ARCHIVE_NAME) slp/
	@echo "Created $(ARCHIVE_NAME)"

publish: build
	@echo "Validating version..."
	@BINARY_VERSION=$$($(DIST_DIR)/slp --version 2>&1 | awk '{print $$NF}'); \
	if [ "$$BINARY_VERSION" != "$(VERSION)" ]; then \
		echo "ERROR: Binary version ($$BINARY_VERSION) does not match expected version ($(VERSION))"; \
		exit 1; \
	fi
	@echo "Version validated: $(VERSION)"
	@echo "Uploading to $(GCS_PATH)..."
	gsutil cp $(ARCHIVE_NAME) $(GCS_PATH)
	@rm -f $(ARCHIVE_NAME)
	@echo "Published to $(GCS_PATH)"

clean:
	@echo "Cleaning build artifacts..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@rm -rf .pytest_cache
	@rm -rf .ruff_cache
	@rm -rf *.egg-info
	@rm -rf build dist $(ARCHIVE_NAME)
	@echo "Cleaned"

update: update-darwin-arm64 update-linux-amd64
	@echo "Updated shasums for all platforms"

update-darwin-arm64:
	@echo "Downloading darwin arm64 archive..."
	@mkdir -p tmp
	@curl -fL $(BASE_URL)/darwin/arm64/slp.tar.gz -o tmp/slp-darwin-arm64.tar.gz
	@echo "Computing shasum for darwin arm64..."
	@SHASUM=$$(shasum -a 256 tmp/slp-darwin-arm64.tar.gz | awk '{print $$1}'); \
		echo "Darwin arm64 SHA256: $$SHASUM"; \
		$(SED_INPLACE) "s/^DARWIN_ARM64_SHA256=\".*\"/DARWIN_ARM64_SHA256=\"$$SHASUM\"/" $(INSTALL_SCRIPT)
	@rm -rf tmp

update-linux-amd64:
	@echo "Downloading linux amd64 archive..."
	@mkdir -p tmp
	@curl -fL $(BASE_URL)/linux/amd64/slp.tar.gz -o tmp/slp-linux-amd64.tar.gz
	@echo "Computing shasum for linux amd64..."
	@SHASUM=$$(sha256sum tmp/slp-linux-amd64.tar.gz | awk '{print $$1}'); \
		echo "Linux amd64 SHA256: $$SHASUM"; \
		$(SED_INPLACE) "s/^LINUX_AMD64_SHA256=\".*\"/LINUX_AMD64_SHA256=\"$$SHASUM\"/" $(INSTALL_SCRIPT)
	@rm -rf tmp

update-version:
	@echo "Updating VERSION in install.sh to $(VERSION)..."
	@$(SED_INPLACE) "s/^VERSION=\".*\"/VERSION=\"$(VERSION)\"/" $(INSTALL_SCRIPT)


.DEFAULT_GOAL := help
