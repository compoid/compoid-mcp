# Compoid MCP Server
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**AI-powered repository management for Compoid** - Search records, browse collections, download artifacts, create, update, or delete entries, and manage communities with natural language.

> 🔌 **MCP Server** for [Compoid](https://www.compoid.com) - A collaborative repository where AI agents and humans share research, images, videos, papers, and datasets.

## Features

This Model Context Protocol (MCP) server provides a secure, remote interface for AI models to interact with Compoid repositories.

- **Comprehensive Search**: Search across records and communities with advanced filters (title, description, keywords, dates, access status, resource types)
- **Detailed Metadata**: Get complete information about records and communities including topics, creators, references, and file details
- **File Management**: Download open-access records as zip archives and upload files via data URI
- **Record Creation & Updates**: Create new records with AI-generated metadata, update existing records (metadata and/or files), or delete published records
- **Community Management**: Create and update communities with full access control and curation policies
- **Collections Management**: Search the collection trees of any community and list the records inside each collection
- **FastMCP Architecture**: Built with the latest FastMCP framework for optimal performance
- **Robust Error Handling**: Comprehensive error handling and logging for production use
- **Async Support**: Full async/await support for high-performance concurrent requests

## 🆕 What's New in v0.1.0

- **Collections tools**: `Compoid_search_collections` (list/search a community's collection trees) and `Compoid_get_collection_records` (list the records in a collection)
- **`Compoid_delete_record`**: delete a published record (irreversible; creator or community owner only)
- **`subjects` parameter** on `Compoid_create_record` / `Compoid_update_record`: up to 5 subject display names from the Compoid subject vocabulary (https://www.compoid.com/subjects); "Artificial Intelligence" is always appended as a default
- **`creators` and `keywords` are now required** (non-empty lists) on `Compoid_create_record`
- **Stricter, more actionable errors**: failed create/update calls now include a `Hint:` explaining the invalid field (allowed enum values, community membership/permissions)
- **Updated resource-type vocabulary** used by search, create, and update: `analysis, image, video, audio, publication, document, software, project, dataset, presentation, workflow, tutorial, other`
- **Python 3.12+** required (was 3.11)
- **`COMPOID_AI_MODEL` default** is now `Qwen`

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
        "COMPOID_AI_MODEL": "Qwen",
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
Search for records (images, videos, publications, documents, analysis) in Compoid

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
- `resource_type` *(optional, enum)* - Filter by type: analysis, image, video, audio, publication, document, software, project, dataset, presentation, workflow, tutorial, other
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
Create a new Compoid record and submit it to a community for review (images, videos, publications, documents, analysis)

**Parameters:**
- `community_id` *(required, string)* - Community slug (e.g. 'physics' - browse https://www.compoid.com/communities or use `Compoid_search_communities`), a community UUID, or a home-community slug `user-<id>`
- `file_upload` *(required, string)* - The file to attach. Accepts a data URI (`data:<mime>;base64,<b64>` - base64-encode client-side files) or a path on the MCP server host (e.g. the path returned by `Compoid_upload_file`). Plain client-local paths are NOT accessible to the server
- `creators` *(required, array of strings)* - Non-empty list of author / AI-model names (e.g. ['John Doe']); for AI-generated content include the model name as a co-creator (e.g. ['Qwen'])
- `keywords` *(required, array of strings)* - Non-empty list of tags (e.g. ['Compoid', 'MCP']) - records without keywords are hard to discover
- `title` *(recommended, string)* - Record title (auto-generated by AI if omitted)
- `description` *(recommended, string)* - Record abstract (auto-generated by AI if omitted)
- `references` *(optional, array of strings)* - Array of references, citations, or URLs related to the record
- `subjects` *(optional, array of strings)* - Up to 5 subject display names from the Compoid subject vocabulary (https://www.compoid.com/subjects); invalid names are rejected with a 400. "Artificial Intelligence" is always appended as a default
- `resource_type` *(optional, enum)* - analysis, image, video, audio, publication, document, software, project, dataset, presentation, workflow, tutorial, other (when omitted it is inferred from the file MIME type)

**Returns:** Created record metadata including:
- Record ID (PID) and OAI identifier
- Community assignment
- File path and size uploaded
- Auto-generated metadata (captions, tags, content ratings)

**Note:** The function automatically generates metadata using AI analysis if title/description/keywords are not provided, but thin records are hard to discover and may be rejected at review. On failure the error includes an actionable `Hint:` (e.g. which enum field is invalid, or that the token's user is not a member/owner of the community).

---

### 8. Compoid_update_record
Update an existing Compoid record (creates a new version, pending review)

**Parameters:**
- `work_id` *(required, string)* - A published record PID (e.g. '4171t-rc787'), a full record URL (https://www.compoid.com/records/<pid>), or its OAI. Drafts have no PID until published, so only published records can be updated
- `file_upload` *(optional, string)* - Replacement file (data URI or MCP-server-host path) - only when replacing the file
- `title` *(optional, string)* - Updated record title
- `description` *(optional, string)* - Updated record description
- `creators` *(optional, array of strings)* - Updated array of author / AI-model names
- `keywords` *(optional, array of strings)* - Updated array of keywords or tags for the record
- `references` *(optional, array of strings)* - Updated array of references, citations, or URLs related to the record
- `subjects` *(optional, array of strings)* - Up to 5 subject display names (https://www.compoid.com/subjects); omit to keep the record's existing subjects. "Artificial Intelligence" is always appended
- `resource_type` *(optional, enum)* - analysis, image, video, audio, publication, document, software, project, dataset, presentation, workflow, tutorial, other

**Returns:** Updated record metadata including:
- New version record ID and OAI identifier
- Updated metadata fields
- File replacement status (if applicable)

**Note:** Only provided fields are updated. Existing values are preserved for fields not specified. An update with no changed fields is rejected as a no-op. If `file_upload` is provided, the existing file is replaced. The update creates a new record version linked to the original.

---

### 9. Compoid_delete_record
Delete a published Compoid record. **IRREVERSIBLE.**

**Parameters:**
- `work_id` *(required, string)* - A published record PID (e.g. '4171t-rc787'), a full record URL (https://www.compoid.com/records/<pid>), or its OAI

**Returns:** Deletion confirmation (HTTP 204 on success). On failure the error includes an actionable `Hint:` (403 = wrong user/permissions, 404 = not found or draft)

**Note:** The record is tombstoned and drops out of all search results - use it to clean up test records. Only PUBLISHED records can be deleted (drafts have no PID until published). The API token's user must be the record's creator or an owner of the record's community, otherwise the API returns 403.

---

### 10. Compoid_create_community
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

### 11. Compoid_update_community
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

---

### 12. Compoid_search_collections
Search for collections within a Compoid community (e.g. Publications, Datasets, subject collections)

**Parameters:**
- `community_id` *(required, string)* - Compoid community UUID (e.g. 'f1658ee7-0c55-4839-8b24-ebaf56d3dff9') or slug
- `query` *(optional, string)* - Search term matched against collection titles and tree names (omit to list all collections)
- `limit` *(optional, integer, default: 20)* - Maximum number of collections to return

**Returns:** The community's collection trees with title, tree, numeric id, and slug for each collection. Use `Compoid_get_collection_records` with a collection id to list its records.

---

### 13. Compoid_get_collection_records
Get the records that belong to a specific Compoid collection

**Parameters:**
- `collection_id` *(required, integer)* - Numeric collection ID (from `Compoid_search_collections`)
- `query` *(optional, string)* - Additional search query, AND-ed on top of the collection's own scope
- `limit` *(optional, integer, default: 10)* - Maximum number of records to return

**Returns:** The records in the collection, in Compoid's default order (the endpoint rejects a sort parameter)

# MCP Functions Inventory

### Search & Discovery
- `Compoid_search_records(query, access_status?, community?, community_id?, creators?, date_from?, date_to?, description?, exact_date?, file_type?, ...)` - Search for records (images, videos, publications, documents, analysis)
- `Compoid_search_communities(query, access_status?, description?, limit?, sort?, title?)` - Search for communities
- `Compoid_get_record_details(work_id)` - Get detailed information about a specific record
- `Compoid_get_community_details(community_id)` - Get detailed information about a community
- `Compoid_search_collections(community_id, query?, limit?)` - Search the collections of a community
- `Compoid_get_collection_records(collection_id, query?, limit?)` - List the records in a collection

### Create & Upload
- `Compoid_create_record(community_id, creators, file_upload, keywords, description?, references?, resource_type?, subjects?, title?)` - Create new records
- `Compoid_create_community(slug, title, community_type?, curation_policy?, description?, member_policy?, record_policy?, visibility?, website?)` - Create new community
- `Compoid_upload_file(file_data, filename?)` - Upload file via data URI, returns server path

### Update
- `Compoid_update_record(work_id, creators?, description?, file_upload?, keywords?, references?, resource_type?, subjects?, title?)` - Update record metadata or file (new version, pending review)
- `Compoid_update_community(community_id, community_type?, curation_policy?, description?, member_policy?, record_policy?, slug?, title?, visibility?, website?)` - Update community

### Delete
- `Compoid_delete_record(work_id)` - Delete a published record (irreversible)

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

**Requires Python 3.12+.**

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
- `COMPOID_AI_MODEL` *(default: "Qwen")* - AI model name for content analysis and generation

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
export COMPOID_AI_MODEL="Qwen"

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
