APP_NAME = "TIDAL-Downloader-NG"
APP_VERSION=`grep -m 1 'version =' pyproject.toml | tr -s ' ' | tr -d '"' | tr -d "'" | cut -d' ' -f3`
app_path_dist = "dist"
path_asset = "tidal_dl_ng/ui"
APP_BUNDLE_NAME="gui"
DMG_NAME="dmg"

# Nuitka picks the first clang on PATH. A Homebrew LLVM installation shadows Apple clang and does not
# know where the macOS SDK lives, which fails the C backend with "'stdlib.h' file not found".
# Pointing SDKROOT at the active SDK makes either compiler resolve the system headers.
ifeq ($(shell uname -s),Darwin)
SDKROOT ?= $(shell xcrun --show-sdk-path)
export SDKROOT
endif

.PHONY: install
install: ## Install the poetry environment and install the pre-commit hooks
	@echo "🚀 Creating virtual environment using pyenv and poetry"
	@poetry install
	@poetry run pre-commit install
	@poetry shell

.PHONY: check
check: ## Run code quality tools.
	@echo "🚀 Checking Poetry lock file consistency with 'pyproject.toml': Running poetry lock --check"
	@poetry check --lock
	@echo "🚀 Linting code: Running pre-commit"
	@poetry run pre-commit run -a
#	@echo "🚀 Static type checking: Running mypy"
#	@poetry run mypy
	@echo "🚀 Checking for obsolete dependencies: Running deptry"
	@poetry run deptry .

.PHONY: test
test: ## Test the code with pytest
	@echo "🚀 Testing code: Running pytest"
	@poetry run pytest --doctest-modules

.PHONY: build
build: clean-build ## Build wheel file using poetry
	@echo "🚀 Creating wheel file"
	@poetry build

.PHONY: clean-build
clean-build: ## clean build artifacts
	@rm -rf dist

.PHONY: publish
publish: ## publish a release to pypi.
	@echo "🚀 Publishing: Dry run."
	@poetry config pypi-token.pypi $(PYPI_TOKEN)
	@poetry publish --dry-run
	@echo "🚀 Publishing."
	@poetry publish

.PHONY: build-and-publish
build-and-publish: build publish ## Build and publish.

.PHONY: docs-test
docs-test: ## Test if documentation can be built without warnings or errors
	@poetry run mkdocs build -s

.PHONY: docs
docs: ## Build and serve the documentation
	@poetry run mkdocs serve

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: gui
gui: ## Build GUI app
	@poetry run python -m nuitka \
		--macos-app-version=$(APP_VERSION) \
		--file-version=$(APP_VERSION) \
		--product-version=$(APP_VERSION) \
		--macos-app-name=$(APP_NAME) \
		--output-filename=$(APP_NAME) \
		--product-name=$(APP_NAME) \
		tidal_dl_ng/gui.py

.PHONY: gui-windows
gui-windows: gui ## Build GUI app
	@poetry run mv "$(app_path_dist)/$(APP_BUNDLE_NAME).dist" "$(app_path_dist)/$(APP_NAME)"

.PHONY: gui-linux
gui-linux: gui ## Build GUI app
	@poetry run mv "$(app_path_dist)/$(APP_BUNDLE_NAME).dist" "$(app_path_dist)/$(APP_NAME)"

.PHONY: check-macos-python
check-macos-python: ## Reject an interpreter that makes Nuitka scan the Homebrew prefix
	@poetry run python -c "from nuitka.PythonFlavors import isHomebrewPython; raise SystemExit(1 if isHomebrewPython() else 0)" || { \
		echo "Refusing to build with a Homebrew Python."; \
		echo "Nuitka adds every subdirectory of the Homebrew prefix to the library search path, so an"; \
		echo "unrelated PySide6 under /opt/homebrew supplies the Qt libraries while the extension"; \
		echo "modules come from this environment. The bundle then aborts at startup on a missing symbol."; \
		echo "Switch to a non-Homebrew interpreter, for instance:"; \
		echo "    poetry env use /usr/local/bin/python3.12"; \
		exit 1; \
	}

# TODO: macos Signing: https://gist.github.com/txoof/0636835d3cc65245c6288b2374799c43
.PHONY: gui-macos-dmg
gui-macos-dmg: check-macos-python gui ## Package GUI in a *.dmg file
	@rm -rf "$(app_path_dist)/$(DMG_NAME)" "$(app_path_dist)/$(APP_NAME).dmg"
	@mkdir -p $(app_path_dist)/dmg
	@mv "$(app_path_dist)/$(APP_BUNDLE_NAME).app" "$(app_path_dist)/$(DMG_NAME)/$(APP_NAME).app"
	@poetry run create-dmg \
                --volname "$(APP_NAME)" \
                --volicon "$(path_asset)/icon.icns" \
                --window-pos 200 120 \
                --window-size 800 600 \
                --icon-size 100 \
                --icon "$(APP_NAME).app" 175 120 \
                --hide-extension "$(APP_NAME).app" \
                --app-drop-link 425 120 \
                "$(app_path_dist)/$(APP_NAME).dmg" \
                "$(app_path_dist)/$(DMG_NAME)/"

.DEFAULT_GOAL := help
