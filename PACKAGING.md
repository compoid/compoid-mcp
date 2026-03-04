# Compoid MCP Server - Packaging Guide

This guide provides comprehensive instructions for building, testing, and distributing the Compoid MCP Server package.

## Prerequisites

Before building the package, ensure you have the following installed:

```bash
# Python 3.11 or higher
python3 --version

# Required build tools
pip install build twine check-wheel-contents
```

## Package Structure

```
compoid-mcp/
├── pyproject.toml          # Package configuration
├── setup.py                # Legacy setup (if needed)
├── src/
│   └── compoid_mcp/
│       ├── __init__.py
│       ├── server.py       # Main MCP server
│       ├── client.py       # API client
│       ├── config.py       # Configuration
│       ├── tools.py        # MCP tool implementations
│       └── templates/      # Jinja2 templates
├── tests/                  # Test suite
├── README.md
├── LICENSE
└── MANIFEST.in            # Files to include in source distribution
```

## Building the Package

### 1. Build Source Distribution and Wheel

```bash
# Navigate to package root
cd /path/to/compoid-mcp

# Clean previous builds
rm -rf build dist *.egg-info

# Build both sdist and wheel
python -m build

# Or build individually
python -m build --sdist    # Source distribution only
python -m build --wheel    # Wheel only
```

This creates:
- `dist/compoid_mcp-1.0.0.tar.gz` (source distribution)
- `dist/compoid_mcp-1.0.0-py3-none-any.whl` (wheel)

### 2. Verify Package Contents

#### Check Source Distribution

```bash
# List contents
tar -tzf dist/compoid_mcp-1.0.0.tar.gz

# Extract and inspect
tar -xzf dist/compoid_mcp-1.0.0.tar.gz
ls -la compoid_mcp-1.0.0/
```

**Expected contents:**
```
compoid_mcp-1.0.0/
├── PKG-INFO
├── pyproject.toml
├── README.md
├── LICENSE
├── MANIFEST.in
└── src/
    └── compoid_mcp/
        ├── __init__.py
        ├── server.py
        ├── client.py
        ├── config.py
        ├── tools.py
        └── templates/
```

#### Check Wheel Contents

```bash
# List wheel contents
unzip -l dist/compoid_mcp-1.0.0-py3-none-any.whl

# Extract and inspect
unzip -d compoid_mcp_wheel dist/compoid_mcp-1.0.0-py3-none-any.whl
ls -la compoid_mcp_wheel/
```

**Expected contents:**
```
compoid_mcp-1.0.0.dist-info/
├── METADATA
├── WHEEL
├── top_level.txt
├── RECORD
└── compoid_mcp-1.0.0.data/
    └── scripts/
        └── compoid-mcp

compoid_mcp/
├── __init__.py
├── server.py
├── client.py
├── config.py
└── tools.py
```

## Package Validation

### 1. Check Wheel Quality

```bash
# Install check-wheel-contents if not already installed
pip install check-wheel-contents

# Check for common issues
check-wheel-contents dist/compoid_mcp-1.0.0-py3-none-any.whl

# Check with strict mode
check-wheel-contents -v dist/compoid_mcp-1.0.0-py3-none-any.whl
```

### 2. Validate with Twine

```bash
# Check package metadata
twine check dist/compoid_mcp-1.0.0.tar.gz dist/compoid_mcp-1.0.0-py3-none-any.whl

# Expected output:
# WARNING  'requires-python' not specified.
#         The wheel will not be installable on Python versions outside the default range.
#         This is not a fatal error, but you should consider specifying 'requires-python'.
#
# =========
# No issues found
```

### 3. Test Installation

#### Test Wheel Installation

```bash
# Create clean virtual environment
python -m venv test_env
source test_env/bin/activate

# Install from wheel
pip install dist/compoid_mcp-1.0.0-py3-none-any.whl

# Verify installation
python -c "import compoid_mcp; print(compoid_mcp.__version__)"
python -m compoid_mcp.server --help
```

#### Test Source Distribution Installation

```bash
# Create clean virtual environment
python -m venv test_env2
source test_env2/bin/activate

# Install from source
pip install dist/compoid_mcp-1.0.0.tar.gz

# Verify installation
python -c "import compoid_mcp; print(compoid_mcp.__version__)"
```

## Local Development Installation

### Editable Install (Recommended for Development)

```bash
# Install in editable mode with development dependencies
pip install -e ".[dev]"

# This installs:
# - The package itself in editable mode
# - All runtime dependencies
# - Development dependencies (testing, linting, etc.)
```

### Verify Development Installation

```bash
# Check package is installed
pip show compoid-mcp

# Run tests
pytest tests/

# Run linter
ruff check src/

# Run type checker
mypy src/
```

## Publishing to PyPI

### 1. Prepare for Release

```bash
# Update version in pyproject.toml
# Example: version = "1.0.1"

# Rebuild packages
python -m build

# Validate packages
twine check dist/*
```

### 2. Upload to TestPyPI (Recommended First)

```bash
# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Enter your TestPyPI username and API token
# Token format: pypi-test-A...
```

### 3. Test TestPyPI Installation

```bash
# Create clean virtual environment
python -m venv test_pypi_env
source test_pypi_env/bin/activate

# Install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple compoid-mcp

# Verify installation
python -c "import compoid_mcp; print(compoid_mcp.__version__)"
```

### 4. Upload to PyPI

```bash
# Upload to production PyPI
twine upload dist/*

# Enter your PyPI username and API token
# Token format: pypi-A...
```

**Important:** Never upload to production PyPI without testing on TestPyPI first!

## Version Management

### Semantic Versioning

This package follows [Semantic Versioning](https://semver.org/):

- **MAJOR** version for incompatible API changes
- **MINOR** version for backwards-compatible functionality
- **PATCH** version for backwards-compatible bug fixes

### Updating Version

1. Edit `pyproject.toml`:
   ```toml
   [project]
   version = "1.0.1"  # Update this
   ```

2. Update `CHANGELOG.md` with release notes

3. Create git tag:
   ```bash
   git tag -a v1.0.1 -m "Release version 1.0.1"
   git push origin v1.0.1
   ```

## Package Metadata

### pyproject.toml Configuration

Key configuration sections:

```toml
[project]
name = "compoid-mcp"
version = "1.0.0"
description = "Model Context Protocol server for Compoid AI database"
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.11"
authors = [
    { name = "Compoid Team", email = "team@compoid.com" }
]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]
dependencies = [
    "httpx>=0.27.0",
    "fastmcp>=0.1.0",
    "jinja2>=3.1.0",
    "requests>=2.31.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
    "build>=0.10.0",
    "twine>=4.0.0",
]

[project.scripts]
compoid-mcp = "compoid_mcp.server:main"

[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"
```

## Troubleshooting

### Common Issues

#### 1. "Module not found" errors

```bash
# Ensure you're in the package root directory
cd /path/to/compoid-mcp

# Reinstall in editable mode
pip install -e ".[dev]"
```

#### 2. Wheel validation failures

```bash
# Check for common issues
check-wheel-contents -v dist/*.whl

# Fix: Ensure MANIFEST.in includes all necessary files
cat MANIFEST.in
```

#### 3. Template files not included

```bash
# Ensure MANIFEST.in includes templates:
cat >> MANIFEST.in << EOF
recursive-include src/compoid_mcp/templates *.json
EOF

# Rebuild
python -m build
```

#### 4. PyPI upload rejected

```bash
# Check package metadata
twine check dist/*

# Verify no sensitive data in package
grep -r "API_KEY\|SECRET\|TOKEN" src/
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Build and Test

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install build twine pytest pytest-asyncio
      
      - name: Build package
        run: python -m build
      
      - name: Check package
        run: twine check dist/*
      
      - name: Run tests
        run: pytest tests/
      
      - name: Upload artifacts
        uses: actions/upload-artifact@v3
        with:
          name: package
          path: dist/
```

## Release Checklist

- [ ] Update version in `pyproject.toml`
- [ ] Update `CHANGELOG.md` with release notes
- [ ] Run all tests: `pytest tests/`
- [ ] Run linter: `ruff check src/`
- [ ] Run type checker: `mypy src/`
- [ ] Build packages: `python -m build`
- [ ] Validate packages: `twine check dist/*`
- [ ] Test on TestPyPI
- [ ] Verify TestPyPI installation
- [ ] Upload to PyPI
- [ ] Create git tag
- [ ] Update documentation if needed

## Support

For issues or questions:
- **GitHub Issues**: https://github.com/compoid/compoid-mcp/issues
- **Documentation**: https://www.compoid.com/documentation
- **Website**: https://www.compoid.com/