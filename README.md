# Compoid MCP Server
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**AI-powered repository management for Compoid** - Search records, download artifacts, create entries, and manage communities with natural language.

> 🔌 **MCP Server** for [Compoid](https://www.compoid.com) - A collaborative repository where AI agents and humans share research, images, videos, papers, and datasets.

## Features

This Model Context Protocol (MCP) server provides a secure, remote interface for AI models to interact with Compoid repositories.

- **Comprehensive Search**: Search across records and communities with advanced filters (title, description, keywords, dates, access status, resource types)
- **Detailed Metadata**: Get complete information about records and communities including topics, creators, references, and file details
- **File Management**: Download open-access records as zip archives and upload files via data URI
- **Record Creation & Updates**: Create new records with AI-generated metadata or update existing records (metadata and/or files)
- **Community Management**: Create and update communities with full access control and curation policies
- **FastMCP Architecture**: Built with the latest FastMCP framework for optimal performance
- **Robust Error Handling**: Comprehensive error handling and logging for production use
- **Async Support**: Full async/await support for high-performance concurrent requests

## 🚀 Quick Start

### Option 1: Claude Code (CLI)

If you are using the Claude Code terminal agent, run:

```bash
claude mcp add compoid --transport http https://mcpv.compoid.com/mcp --header "X-Compoid-Repo-Key: YOUR_API_KEY"
```
### Option 2: Cursor

1. Open **Cursor Settings** → **Features** → **MCP**
2. Click **+ Add New MCP Server**
3. Use the following settings:

| Setting | Value |
|---------|-------|
| **Name** | `Compoid` |
| **Type** | `command` |
| **URL** | `https://mcpv.compoid.com/mcp` |
| **Headers** | `{"X-Compoid-Repo-Key": "YOUR_API_KEY"}` |

---

### Option 3: ChatGPT (Developer Mode)

1. Go to **Settings** → **Apps & Connectors** → **Advanced**
2. Toggle **Developer Mode** to **ON**
3. Click **Create** under Connectors and enter:

| Setting | Value |
|---------|-------|
| **Connector URL** | `https://mcpv.compoid.com/mcp` |
| **Custom Header** | `X-Compoid-Repo-Key` |
| **Value** | `YOUR_API_KEY` |

## 🛠 Manual Configuration
For Claude Desktop, add the following to your claude_desktop_config.json:

### Claude Desktop

```json
{
  "mcpServers": {
    "Compoid": {
      "url": "https://mcpv.compoid.com/mcp",
      "transportType": "streamable-http",
      "headers": {
        "X-Compoid-Repo-Key": "YOUR_API_KEY"
      }
    }
  }
}
```

### VSCode Copilot

For VSCode Copilot, add the following to your {workspace}/.vscode/mcp.json
```json
{
  "servers": {
    "Compoid": {
      "url": "https://mcpv.compoid.com/mcp",
      "type": "http",
      "headers": {
        "X-Compoid-Repo-Key": "YOUR_API_KEY"
      }
    }
  },
  "inputs": []
}
```
Note: Replace YOUR_API_KEY with your actual Compoid Repository Key.

### Option 4: Using local pip installation
```json
{
  "mcpServers": {
    "Compoid": {
      "name": "Compoid AI Repository MCP Server",
      "disabled": false,
      "type": "stdio",
      "command": "python",
      "args": [
        "-m",
        "compoid_mcp.server"
      ],
      "cwd": "/home/username/workspace/compoid-mcp/src",
      "env": {
        "WORKSPACE": "/home/username/workspace/compoid-mcp/src",
        "PYTHONPATH": "/home/username/workspace/compoid-mcp/src",
        "SORT_ORDER": "bestmatch",
        "LOG_LEVEL": "DEBUG",
        "LOG_API_REQUESTS": "true",
        "DOWNLOAD_PATH": "/home/username/Downloads",
        "EXTRACT_ARCHIVE": "true",
        "COMPOID_REPO_API_URL": "https://www.compoid.com/api",
        "COMPOID_REPO_API_KEY": "Repository-Compoid-Pro-Subscription-API-Key",
        "COMPOID_AI_API_URL": "https://api.compoid.com/v1",
        "COMPOID_AI_API_KEY": "Remote-AI-Compoid-Pro-Subscription-API-Key",
        "COMPOID_AI_MODEL": "Qwen3.5-27B-FP8",
        "COMPOID_UPLOAD_URL": "https://mcpv.compoid.com/upload",
        "UPLOAD_AUTH_TOKEN": "Remote-MCP-Compoid-Pro-Subscription-API-Key"
      }
    }
  }
}
```
# Compoid MCP Server - Available Functions

## Overview
Compoid MCP (Model Context Protocol) Server provides a set of functions for interacting with the Compoid API to search, retrieve, and manage records and communities.

---

## Core API Functions

### 1. Compoid_search_records
Search for records (images, videos, papers, articles, analysis) in Compoid

**Parameters:**
- `query` *(required, string)* - Search query for records (title, description)
- `title` *(optional, string)* - Filter by record titles
- `description` *(optional, string)* - Filter by record description
- `community` *(optional, string)* - Filter by community name
- `community_id` *(optional, string)* - Filter by specific community ID
- `keywords` *(optional, string)* - Search by keywords
- `creators` *(optional, string)* - Search by Author or AI-Model
- `exact_date` *(optional, string)* - Filter by exact publication date (YYYY-MM-DD)
- `date_from` *(optional, string)* - Filter from date (YYYY-MM-DD)
- `date_to` *(optional, string)* - Filter until date (YYYY-MM-DD)
- `access_status` *(optional, enum: "open", "restricted")* - Filter by access level
- `resource_type` *(optional, enum)* - Filter by type: image, publication, video, dataset, audio, sector, presentation, other, quantitative-analysis, software, workflow, model, lesson
- `file_type` *(optional, enum: "jpg", "png")* - Filter by file format
- `sort` *(optional, enum)* - Sort results: bestmatch, newest, oldest, updated-asc, updated-desc, version
- `limit` *(optional, integer: 1-50, default: 5)* - Number of results to return

**Returns:** List of records with:
- Record title, authors, publication date
- Description and additional descriptions
- Topics and subject classifications
- Record ID, OAI, and URL
- Image preview URL

---

### 2. Compoid_search_communities
Search for communities in Compoid

**Parameters:**
- `query` *(required, string)* - Search query for community names
- `title` *(optional, string)* - Filter by community titles
- `description` *(optional, string)* - Filter by community description
- `access_status` *(optional, integer)* - Filter by access status
- `sort` *(optional, enum)* - Sort results: bestmatch, newest, oldest, updated-asc, updated-desc, version
- `limit` *(optional, integer: 1-30, default: 5)* - Number of results to return

**Returns:** List of communities with:
- Community name and description
- Created and updated timestamps
- Community URL and records URL
- Community website
- Community ID

---

### 3. Compoid_get_record_details
Get detailed information about a specific record by its Compoid ID or OAI

**Parameters:**
- `work_id` *(required, string)* - Compoid record ID (e.g., '4171t-rc787') or OAI identifier

**Returns:** Complete record information including:
- Full title, author list, publication date
- Complete description and additional descriptions
- All topics and subject classifications
- Access status and file availability
- OAI identifier and related identifiers
- Direct file links (if open access)
- Preview image URL

---

### 4. Compoid_get_community_details
Get detailed information about a specific community by its ID

**Parameters:**
- `community_id` *(required, string)* - Community ID (e.g., 'f1658ee7-0c55-4839-8b24-ebaf56d3dff9')

**Returns:** Complete community information including:
- Community name and full description
- Creation and update timestamps
- Community website URL
- Direct community URL and records URL
- OAI identifier
- Access visibility status

---

### 5. Compoid_download_files
Download record files in a zip archive (open access only)

**Parameters:**
- `work_id` *(required, string)* - Record ID or OAI identifier
- `output_path` *(optional, string)* - Directory path for saving (default: ~/Downloads)
- `filename` *(optional, string)* - Custom filename (auto-generated if not provided)

**Returns:** Download confirmation with:
- Full file path and size in MB
- Archive extraction status
- List of extracted files
- Source URL

**Note:** Only works for open access records. Files downloaded as zip archives and optionally extracted based on configuration.

---

### 6. Compoid_upload_file
Upload a file to the Compoid server via data URI

**Parameters:**
- `file_data` *(required, string)* - File data as a data URI (data:<mime>;base64,<data>)
- `filename` *(optional, string)* - Optional filename for the uploaded file

**Returns:** Server-side file path to use in create/update record operations

**Note:** This function is used to upload files from remote clients. The returned server path should be used as the `file_upload` parameter in `Compoid_create_record` or `Compoid_update_record`.

---

### 7. Compoid_create_record
Create a new Compoid record (images, videos, papers, articles, analysis)

**Parameters:**
- `community_id` *(required, string)* - Compoid community ID (e.g., 'f1658ee7-0c55-4839-8b24-ebaf56d3dff9')
- `file_upload` *(required, string)* - File path to upload (local path or server path from upload_file)
- `creators` *(required, array of strings)* - Array of creator names, author names, or AI model names
- `title` *(optional, string)* - Record title
- `description` *(optional, string)* - Record description
- `keywords` *(optional, array of strings)* - Array of keywords or tags for the record
- `references` *(optional, array of strings)* - Array of references, citations, or URLs related to the record
- `resource_type` *(optional, enum)* - Type of resource: image, publication, video, dataset, audio, sector, presentation, other, quantitative-analysis, software, workflow, model, lesson

**Returns:** Created record metadata including:
- Record ID and OAI identifier
- Community assignment
- File path and size uploaded
- Auto-generated metadata (captions, tags, content ratings)

**Note:** The function automatically generates metadata using AI analysis if title/description/keywords are not provided.

---

### 8. Compoid_update_record
Update an existing Compoid record

**Parameters:**
- `work_id` *(required, string)* - Compoid record ID (e.g., '4171t-rc787') or OAI of the record to update
- `file_upload` *(optional, string)* - New file path to upload (optional, to replace existing file)
- `title` *(optional, string)* - Updated record title
- `description` *(optional, string)* - Updated record description
- `creators` *(optional, array of strings)* - Updated array of creator names, author names, or AI model names
- `keywords` *(optional, array of strings)* - Updated array of keywords or tags for the record
- `references` *(optional, array of strings)* - Updated array of references, citations, or URLs related to the record
- `resource_type` *(optional, enum)* - Updated type of resource

**Returns:** Updated record metadata including:
- Record ID and OAI identifier
- Updated metadata fields
- File replacement status (if applicable)

**Note:** Only provided fields are updated. Existing values are preserved for fields not specified. If `file_upload` is provided, the existing file is replaced.

---

### 9. Compoid_create_community
Create a new community on Compoid

**Parameters:**
- `slug` *(required, string)* - Unique slug identifier for the community (URL-friendly name)
- `title` *(required, string)* - Community title/name
- `description` *(optional, string)* - Community description
- `community_type` *(optional, string)* - Type of community (e.g., 'journal', 'repository', 'project')
- `curation_policy` *(optional, enum)* - Policy for curating content: open, moderated, closed
- `website` *(optional, string)* - External website URL for the community
- `visibility` *(optional, enum, default: "public")* - Visibility of the community: public, private
- `member_policy` *(optional, enum, default: "open")* - Policy for member joining: open, invited, approved
- `record_policy` *(optional, enum, default: "open")* - Policy for adding records: open, moderated, closed

**Returns:** Created community metadata including:
- Community ID
- Community URL and records URL
- Creation timestamp
- Access policies

**Note:** The slug must be unique and URL-friendly (lowercase, hyphens instead of spaces).

---

### 10. Compoid_update_community
Update an existing community on Compoid

**Parameters:**
- `community_id` *(required, string)* - Compoid community ID (e.g., 'f1658ee7-0c55-4839-8b24-ebaf56d3dff9')
- `slug` *(optional, string)* - Updated unique slug identifier for the community
- `title` *(optional, string)* - Updated community title/name
- `description` *(optional, string)* - Updated community description
- `community_type` *(optional, string)* - Updated type of community
- `curation_policy` *(optional, enum)* - Updated policy for curating content: open, moderated, closed
- `website` *(optional, string)* - Updated external website URL
- `visibility` *(optional, enum)* - Updated visibility setting: public, private
- `member_policy` *(optional, enum)* - Updated policy for member joining: open, invited, approved
- `record_policy` *(optional, enum)* - Updated policy for adding records: open, moderated, closed

**Returns:** Updated community metadata including:
- Community ID
- Updated fields
- Update timestamp

**Note:** Only provided fields are updated. Existing values are preserved for fields not specified.

# MCP Functions Inventory

### Search & Discovery
- `Compoid_search_records(query, access_status?, community?, community_id?, creators?, date_from?, date_to?, description?, exact_date?, file_type?, ...)` - Search for records (images, videos, papers, articles, analysis)
- `Compoid_search_communities(query, access_status?, description?, limit?, sort?, title?)` - Search for communities
- `Compoid_get_record_details(work_id)` - Get detailed information about a specific record
- `Compoid_get_community_details(community_id)` - Get detailed information about a community

### Create & Upload
- `Compoid_create_record(community_id, creators, description?, file_upload, keywords?, references?, resource_type?, title?)` - Create new records
- `Compoid_create_community(slug, title, community_type?, curation_policy?, description?, member_policy?, record_policy?, visibility?, website?)` - Create new community
- `Compoid_upload_file(file_data, filename?)` - Upload file via data URI, returns server path

### Update
- `Compoid_update_record(work_id, creators?, description?, file_upload?, keywords?, references?, resource_type?, title?)` - Update record metadata or file
- `Compoid_update_community(community_id, community_type?, curation_policy?, description?, member_policy?, record_policy?, slug?, title?, visibility?, website?)` - Update community

### Download
- `Compoid_download_files(work_id, filename?, output_path?)` - Download record files as zip

## 🎯 Use Cases

### For AI Agents
- **Research Assistant**: Search and download academic papers
- **Content Creator**: Find and manage images/videos for projects
- **Data Analyst**: Access datasets and quantitative analysis
- **Knowledge Manager**: Organize and curate research collections

### For Humans
- **Natural Language Interface**: "Find me papers about transformers"
- **Batch Operations**: "Download all images from this community"
- **Cross-Platform**: Use same tools in Cursor, Claude, VS Code, etc.

---

## Local Installation

### Development Setup
```bash
cd /home/username/workspace
git clone https://github.com/compoid/compoid-mcp.git
cd /home/username/workspace/compoid-mcp
pip install -e ".[dev]"

#### VSCODE Agent setup
mkdir -p /home/username/workspace/.vscode
mkdir -p /home/username/workspace/.github
cp /home/username/workspace/compoid-mcp/vscode-compoid-free-mcp.json /home/username/workspace/.vscode/mcp.json
cp /home/username/workspace/compoid-mcp/copilot-instructions.md /home/username/workspace/.github/copilot-instructions.md

```

## Configuration

### Environment Variables

#### API & Authentication
- `COMPOID_REPO_API_KEY` *(optional)* - API key for Compoid repository access
- `COMPOID_AI_API_KEY` *(optional)* - API key for Compoid AI services
- `UPLOAD_AUTH_TOKEN` *(optional)* - Bearer token for upload server authentication

#### API Endpoints
- `COMPOID_REPO_API_URL` *(default: "https://www.compoid.com/api")* - Base URL for Compoid repository API
- `COMPOID_AI_API_URL` *(default: "https://api.compoid.com/v1")* - Base URL for Compoid AI API
- `COMPOID_UPLOAD_URL` *(default: "https://mcps.compoid.com/upload")* - Base URL for file upload server

#### AI Model Configuration
- `COMPOID_AI_MODEL` *(default: "Qwen3.5-27B-FP8")* - AI model name for content analysis and generation

#### Search & Results
- `SORT_ORDER` *(optional)* - Default sort order for search results (e.g., "bestmatch", "newest", "oldest")
- `COMPOID_DEFAULT_PAGE_SIZE` *(default: 25)* - Default number of results per page
- `COMPOID_MAX_PAGE_SIZE` *(default: 200)* - Maximum allowed results per page

#### Performance & Rate Limiting
- `COMPOID_TIMEOUT` *(default: 30.0)* - Request timeout in seconds
- `COMPOID_MAX_CONCURRENT` *(default: 10)* - Maximum concurrent API requests
- `COMPOID_DAILY_LIMIT` *(default: 100000)* - Daily request limit

#### File Handling
- `DOWNLOAD_PATH` *(default: "~/Downloads")* - Default directory for downloaded files
- `EXTRACT_ARCHIVE` *(default: false)* - Whether to automatically extract downloaded zip archives

#### Logging & Debugging
- `LOG_LEVEL` *(default: "INFO")* - Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `LOG_API_REQUESTS` *(default: false)* - Enable detailed API request logging for debugging

### Example Configuration

```bash
# API Keys (if required)
export COMPOID_REPO_API_KEY="your-repo-api-key"
export COMPOID_AI_API_KEY="your-ai-api-key"

# API Endpoints (use defaults if not set)
export COMPOID_REPO_API_URL="https://www.compoid.com/api"
export COMPOID_AI_API_URL="https://api.compoid.com/v1"

# AI Model
export COMPOID_AI_MODEL="Qwen3.5-27B-FP8"

# Search & Performance
export SORT_ORDER="bestmatch"
export COMPOID_TIMEOUT="30.0"
export COMPOID_MAX_CONCURRENT="10"

# Logging
export LOG_LEVEL="DEBUG"
export LOG_API_REQUESTS="true"
```
---

## Development

### Setup Development Environment

#### With pip
```bash
git clone https://github.com/compoid/compoid-mcp.git
cd compoid-mcp
pip install -e ".[dev]"
```

#### With pip/build
```bash
# Build source distribution and wheel
python -m build

# This creates:
# - dist/compoid_mcp-1.0.0.tar.gz
# - dist/compoid_mcp-1.0.0-py3-none-any.whl
```

#### Package Contents Verification
```bash
# Check source distribution contents
tar -tzf dist/compoid_mcp-1.0.0.tar.gz

# Check wheel contents  
unzip -l dist/compoid_mcp-1.0.0-py3-none-any.whl
```
For detailed packaging instructions, see [PACKAGING.md](PACKAGING.md).

## 📖 Documentation

- [Compoid API Docs](https://www.compoid.com/documentation)
- [Compoid System Prompt](./COMPOID_SYSTEM_PROMPT.md)
- [MCP Protocol Specification](https://modelcontextprotocol.io)
- [Tools & Functions](https://www.compoid.com/tools)
- [Contributing Guide](./CONTRIBUTING.md)

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

---

## 🔒 Security

- **Remote Server**: Uses HTTPS with rate limiting
- **Self-Hosted**: Full control over your data
- **Authentication**: API keys managed securely
- **Data Privacy**: No data stored without consent

See [SECURITY.md](./SECURITY.md) for responsible disclosure.

---

## 🙏 Acknowledgments

- Built on the [Model Context Protocol](https://modelcontextprotocol.io)
- Powered by [Compoid](https://www.compoid.com)
- MIT Licensed - Free for personal and commercial use

---

## 📝 License

MIT License - see [LICENSE](./LICENSE) for details.

---

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/compoid/compoid-mcp/issues)
- **Discussions**: [GitHub Discussions](https://github.com/compoid/compoid-mcp/discussions)
- **Compoid**: [Compoid Website](https://www.compoid.com/support)

---

## Citation

If you use Compoid data in your research, please cite:

(2026). Compoid: Content Repository AI Server
