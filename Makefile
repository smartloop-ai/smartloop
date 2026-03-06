VERSION := 1.0.1
BASE_URL := https://storage.googleapis.com/smartloop-gcp-us-east-releases/$(VERSION)
INSTALL_SCRIPT := install.sh

.PHONY: help update update-version update-all clean

help:
	@echo "VERSION=$(VERSION)"
	@echo ""
	@echo "Available targets:"
	@echo "  make update          - Update shasums for all platforms"
	@echo "  make update-version  - Update VERSION in install.sh to match Makefile"
	@echo "  make clean           - Remove downloaded archives"

update: update-darwin-arm64 update-linux-amd64
	@echo "Updated shasums for all platforms"

update-darwin-arm64:
	@echo "Downloading darwin arm64 archive..."
	@mkdir -p tmp
	@curl -fL $(BASE_URL)/darwin/arm64/slp.tar.gz -o tmp/slp-darwin-arm64.tar.gz
	@echo "Computing shasum for darwin arm64..."
	@SHASUM=$$(shasum -a 256 tmp/slp-darwin-arm64.tar.gz | awk '{print $$1}'); \
		echo "Darwin arm64 SHA256: $$SHASUM"; \
		sed -i "s/^DARWIN_ARM64_SHA256=\".*\"/DARWIN_ARM64_SHA256=\"$$SHASUM\"/" $(INSTALL_SCRIPT)
	@rm -rf tmp

update-linux-amd64:
	@echo "Downloading linux amd64 archive..."
	@mkdir -p tmp
	@curl -fL $(BASE_URL)/linux/amd64/slp.tar.gz -o tmp/slp-linux-amd64.tar.gz
	@echo "Computing shasum for linux amd64..."
	@SHASUM=$$(sha256sum tmp/slp-linux-amd64.tar.gz | awk '{print $$1}'); \
		echo "Linux amd64 SHA256: $$SHASUM"; \
		sed -i "s/^LINUX_AMD64_SHA256=\".*\"/LINUX_AMD64_SHA256=\"$$SHASUM\"/" $(INSTALL_SCRIPT)
	@rm -rf tmp

update-version:
	@echo "Updating VERSION in install.sh to $(VERSION)..."
	@sed -i "s/^VERSION=\".*\"/VERSION=\"$(VERSION)\"/" $(INSTALL_SCRIPT)

clean:
	@rm -rf tmp
