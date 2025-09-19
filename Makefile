# Variables
REGISTRY ?= sukisuk
UTILITY_IMAGE ?= $(REGISTRY)/wire-utility-tool
TAG ?= latest

# Platform targets
PLATFORMS = linux/amd64,linux/arm64

.PHONY: help build-utility push-utility test-utility clean setup-buildx

# Default target
help:
	@echo "Available targets:"
	@echo ""
	@echo "Wire Utility Tool:"
	@echo "  build-utility       - Build wire-utility-tool image"
	@echo "  build-utility-multi - Build wire-utility-tool for multiple platforms"
	@echo "  push-utility        - Push wire-utility-tool image"
	@echo "  test-utility        - Test wire-utility-tool image"
	@echo ""
	@echo "Utility:"
	@echo "  clean         - Clean local images"
	@echo "  setup-buildx  - Setup buildx for multi-platform builds"
	@echo ""
	@echo "Variables:"
	@echo "  REGISTRY      - Registry namespace (default: $(REGISTRY))"
	@echo "  TAG           - Image tag (default: $(TAG))"

# ============================================================================
# Wire Utility Tool Targets
# ============================================================================

# Build wire-utility-tool for current platform
build-utility:
	docker build -f Dockerfile.utility -t $(UTILITY_IMAGE):$(TAG) .

# Build wire-utility-tool for multiple platforms
build-utility-multi:
	docker buildx build --platform $(PLATFORMS) -f Dockerfile.utility -t $(UTILITY_IMAGE):$(TAG) .

# Push wire-utility-tool image
push-utility: build-utility
	docker push $(UTILITY_IMAGE):$(TAG)

# Push wire-utility-tool multi-platform
push-utility-multi:
	docker buildx build --platform $(PLATFORMS) -f Dockerfile.utility -t $(UTILITY_IMAGE):$(TAG) --push .

# Test wire-utility-tool image
test-utility:
	@echo "Testing wire-utility-tool image..."
	docker run --rm --entrypoint="" $(UTILITY_IMAGE):$(TAG) bash -c "echo 'Testing tools...' && python3 --version && python2 --version && psql --version && cqlsh --version && mc --version && echo 'Testing es command...' && es usages && echo 'Testing PATH...' && which bash && echo 'All tests passed!'"

# ============================================================================
# Utility Targets
# ============================================================================

# Clean local images
clean:
	docker rmi $(UTILITY_IMAGE):$(TAG) || true
	@echo "Cleaned local images"

# Setup buildx for multi-platform builds
setup-buildx:
	docker buildx create --use --name multiarch || true
	docker buildx inspect --bootstrap
	@echo "Buildx setup complete"

# Remove buildx builder
cleanup-buildx:
	docker buildx rm multiarch || true

# Show current images
show-images:
	@echo "Current images:"
	@docker images | grep -E "($(REGISTRY)|REPOSITORY)" || echo "No matching images found"

# Login to Docker Hub (interactive)
login:
	docker login

# Quick development workflow
dev-utility: build-utility test-utility
	@echo "Development build complete for wire-utility-tool"

# Quick release workflow (build + test + push)
release-utility: build-utility test-utility push-utility
	@echo "Released $(UTILITY_IMAGE):$(TAG)"