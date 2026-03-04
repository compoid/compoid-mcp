# Contributing to Compoid MCP Server

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the Compoid MCP Server project.

## 🎯 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Contributing Guidelines](#contributing-guidelines)
- [Pull Request Process](#pull-request-process)
- [Good First Issues](#good-first-issues)
- [Style Guide](#style-guide)
- [Testing](#testing)
- [Documentation](#documentation)

## 🤝 Code of Conduct

- Be respectful and inclusive
- Welcome newcomers and questions
- Provide constructive feedback
- Focus on what's best for the community

## 🚀 Getting Started

### 1. Fork the Repository

```bash
# Fork on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/compoid-mcp.git
cd compoid-mcp
```

### 2. Set Up Development Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"

# Verify installation
python -m compoid_mcp.server --help
```

### 3. Configure Your Environment

```bash
# Create .env file (never commit this!)
cat > .env << EOF
COMPOID_REPO_API_KEY=your_test_key
COMPOID_AI_API_KEY=your_ai_key
LOG_LEVEL=DEBUG
LOG_API_REQUESTS=true
EOF

# Load environment variables
export $(cat .env | xargs)
```

## 💻 Development Setup

### Project Structure

```
compoid-mcp/
├── src/
│   └── compoid_mcp/
│       ├── __init__.py
│       ├── server.py          # Main MCP server
│       ├── client.py          # API client
│       ├── config.py          # Configuration
│       ├── tools.py           # Tool implementations
│       ├── models.py          # Pydantic models
│       └── templates/         # Jinja2 templates
├── tests/                     # Test suite
├── docs/                      # Documentation
├── pyproject.toml            # Package configuration
├── README.md
└── CONTRIBUTING.md
```

### Running the Server

```bash
# Development mode
python -m src.compoid_mcp.server

# With debugging
LOG_LEVEL=DEBUG python -m src.compoid_mcp.server
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=src/compoid_mcp tests/

# Run specific test file
pytest tests/test_server.py -v

# Run with verbose output
pytest -vvs tests/
```

## 📝 Contributing Guidelines

### Before You Start

1. **Check existing issues** - See if your idea is already discussed
2. **Create an issue** - For major changes, discuss first
3. **Follow conventions** - Match existing code style
4. **Write tests** - All features need tests
5. **Update docs** - Keep documentation in sync

### Making Changes

1. **Create a branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Follow the style guide
   - Add tests for new features
   - Update documentation

3. **Test your changes**
   ```bash
   pytest tests/
   ```

4. **Commit your changes**
   ```bash
   git commit -m "feat: add new feature"
   ```

5. **Push and create PR**
   ```bash
   git push origin feature/your-feature-name
   ```

## 🔀 Pull Request Process

### PR Requirements

- [ ] Tests pass locally
- [ ] Code follows style guide
- [ ] Documentation updated
- [ ] Changelog updated (if applicable)
- [ ] PR title follows conventional commits
- [ ] Description explains the change

### PR Template

```markdown
## Description
Brief description of the change

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Added tests
- [ ] Tests pass
- [ ] Manually tested

## Checklist
- [ ] Code follows style guide
- [ ] Self-reviewed code
- [ ] Commented complex code
- [ ] Updated documentation
- [ ] Updated changelog
```

### Review Process

1. **Automated checks** - CI must pass
2. **Maintainer review** - Typically within 48 hours
3. **Address feedback** - Make requested changes
4. **Merge** - Squash and merge after approval

## 🏷️ Good First Issues

Perfect for newcomers:

- [ ] **Add TypeScript definitions** for all MCP tools
- [ ] **Write integration tests** for create/update operations
- [ ] **Create example configurations** for different use cases
- [ ] **Add Docker Compose setup** for local development
- [ ] **Write migration guide** from REST API to MCP
- [ ] **Add more resource types** to the enum lists
- [ ] **Improve error messages** for better UX
- [ ] **Add caching layer** for frequently accessed data
- [ ] **Create benchmark tests** for performance
- [ ] **Add more logging levels** for debugging

## 📐 Style Guide

### Python Style

- **Format**: Black (`black src/`)
- **Lint**: Ruff (`ruff check src/`)
- **Type hints**: Required for all functions
- **Docstrings**: Google style

```python
def search_records(query: str, limit: int = 5) -> str:
    """Search for records in Compoid.
    
    Args:
        query: Search query string
        limit: Maximum results to return
        
    Returns:
        Formatted search results
        
    Raises:
        ValueError: If query is empty
    """
    if not query:
        raise ValueError("Query cannot be empty")
    # ... implementation
```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add new MCP tool for file uploads
fix: resolve authentication header issue
docs: update README with examples
test: add unit tests for config module
refactor: simplify error handling
chore: update dependencies
```

### Code Organization

- **One responsibility per function**
- **Meaningful variable names**
- **Comments for complex logic**
- **Type hints everywhere**

## 🧪 Testing

### Writing Tests

```python
# tests/test_server.py
import pytest
from compoid_mcp.server import Compoid_search_records

def test_search_records_with_query():
    """Test search with valid query."""
    result = Compoid_search_records(query="test", limit=1)
    assert result is not None
    assert isinstance(result, str)

def test_search_records_empty_query():
    """Test search with empty query raises error."""
    with pytest.raises(ValueError):
        Compoid_search_records(query="")
```

### Test Coverage

- **Target**: >80% coverage
- **Critical paths**: 100% coverage
- **Run before PR**: `pytest --cov=src/compoid_mcp`

## 📚 Documentation

### What to Document

1. **New features** - Add to README.md
2. **API changes** - Update function docstrings
3. **Configuration** - Document new env vars
4. **Examples** - Add usage examples

### Documentation Standards

- **README.md** - High-level overview
- **Docstrings** - All public functions
- **Comments** - Complex logic only
- **Examples** - Real-world usage

## 🐛 Reporting Bugs

### Bug Report Template

```markdown
**Describe the bug**
Clear description of the bug

**To Reproduce**
Steps to reproduce:
1. Go to '...'
2. Click on '...'
3. See error

**Expected behavior**
What should happen

**Environment**
- OS: [e.g. Ubuntu 22.04]
- Python version: [e.g. 3.10]
- Package version: [e.g. 1.0.0]

**Additional context**
Any other details
```

## 💡 Suggesting Features

### Feature Request Template

```markdown
**Problem**
What problem does this solve?

**Solution**
Proposed solution

**Alternatives**
Alternative solutions considered

**Additional context**
Screenshots, links, etc.
```

## 📖 Resources

- [MCP Protocol Docs](https://modelcontextprotocol.io)
- [Compoid API Docs](https://www.compoid.com/documentation)
- [Python Best Practices](https://docs.python-guide.org/)
- [FastMCP Documentation](https://github.com/punkpeye/fastmcp)

## 🙏 Thank You!

Your contributions make Compoid MCP Server better for everyone. We appreciate your time and effort!

---

**Questions?** Join our [Discussions](https://github.com/compoid/compoid-mcp/discussions) or open an issue.

**Last Updated**: March 4, 2026
