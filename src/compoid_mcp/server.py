"""Compoid MCP Server - Main server implementation using FastMCP."""

import os

from mcp.server.fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers

from compoid_mcp.client import CompoidClient
from compoid_mcp.config import config
from compoid_mcp.tools import (
    download_paper,
    get_work_details,
    get_community_details,
    search_communities,
    search_records,
    create_record,
    update_record,
    upload_file,
    create_community,
    update_community,
)

# Initialize FastMCP server
mcp = FastMCP("compoid-mcp")

sort = os.getenv("SORT_ORDER")


def setup_user_keys_from_headers():
    """Extract user API keys from HTTP headers and configure them."""
    import sys
    headers = get_http_headers()
    
    # Debug logging
    print(f"DEBUG: All headers: {headers}", file=sys.stderr)
    print(f"DEBUG: config.repo_api_key BEFORE: {config.repo_api_key}", file=sys.stderr)
    
    # Check for user-specific API key in headers
    repo_key = headers.get("x-compoid-repo-key")
    ai_key = headers.get("x-compoid-ai-key")
    
    # Extract mcp-proxy Bearer token from Authorization header (used for upload server auth)
    # mcp.json sends the raw token without "Bearer " prefix, so handle both forms
    auth_header = headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        proxy_token = auth_header[7:]
    elif auth_header:
        proxy_token = auth_header
    else:
        proxy_token = None
    
    print(f"DEBUG: Extracted repo_key from header: {repo_key[:10] if repo_key else 'None'}...", file=sys.stderr)
    print(f"DEBUG: Extracted proxy_token from Authorization header: {'set' if proxy_token else 'None'}", file=sys.stderr)

    # Update config if headers are present
    if repo_key or proxy_token:
        config.set_user_api_keys(repo_key=repo_key, ai_key=ai_key, proxy_token=proxy_token)
        print(f"DEBUG: config.repo_api_key AFTER: {config.repo_api_key[:10] if config.repo_api_key else 'None'}...", file=sys.stderr)
    else:
        print(f"DEBUG: No repo_key in headers, using env default: {config.repo_api_key[:10] if config.repo_api_key else 'None'}...", file=sys.stderr)


@mcp.tool(name="Compoid_search_records")
async def Compoid_search_records(
    query: str,
    community_id: str = None,
    title: str = None,
    description: str = None,
    community: str = None,
    keywords: str = None,
    creators: str = None,
    exact_date: str = None,
    date_from: str = None,
    date_to: str = None,
    access_status: str = None,
    resource_type: str = None,
    file_type: str = None,
    sort: str = None,
    limit: int = 5
) -> str:
    """Search for records (images, videos, papers, articles, analysis) in Compoid."""
    setup_user_keys_from_headers()
    client = CompoidClient(sort=sort)
    arguments = {
        "query": query,
        "community_id": community_id,
        "title": title,
        "description": description,
        "community": community,
        "keywords": keywords,
        "creators": creators,
        "exact_date": exact_date,
        "date_from": date_from,
        "date_to": date_to,
        "access_status": access_status,
        "resource_type": resource_type,
        "file_type": file_type,
        "sort": sort,
        "limit": limit
    }
    # Remove None values
    arguments = {k: v for k, v in arguments.items() if v is not None}

    async with client:
        result = await search_records(client, arguments)
        return result[0].text if result else "No results found"


@mcp.tool(name="Compoid_search_communities")
async def Compoid_search_communities(
    query: str,
    title: str = None,
    description: str = None,
    access_status: int = None,
    sort: str = None,
    limit: int = 5
) -> str:
    """Search for communities in Compoid."""
    setup_user_keys_from_headers()
    client = CompoidClient(sort=sort)
    arguments = {
        "query": query,
        "title": title,
        "description": description,
        "access_status": access_status,
        "sort": sort,
        "limit": limit
    }
    # Remove None values
    arguments = {k: v for k, v in arguments.items() if v is not None}

    async with client:
        result = await search_communities(client, arguments)
        return result[0].text if result else "No results found"

@mcp.tool(name="Compoid_get_record_details")
async def Compoid_get_record_details(work_id: str) -> str:
    """Get detailed information about a specific record by its Compoid ID or OAI."""
    setup_user_keys_from_headers()
    client = CompoidClient(sort=sort)
    arguments = {"work_id": work_id}

    async with client:
        result = await get_work_details(client, arguments)
        return result[0].text if result else "record not found"


@mcp.tool(name="Compoid_get_community_details")
async def Compoid_get_community_details(community_id: str) -> str:
    """Get detailed information about a specific community by its Compoid ID or OAI."""
    setup_user_keys_from_headers()
    client = CompoidClient(sort=sort)
    arguments = {"community_id": community_id}

    async with client:
        result = await get_community_details(client, arguments)
        return result[0].text if result else "community not found"


@mcp.tool(name="Compoid_download_files")
async def Compoid_download_files(
    work_id: str,
    output_path: str = "/",
    filename: str = None
) -> str:
    """Download record files in a zip archive if available through open access."""
    setup_user_keys_from_headers()
    client = CompoidClient(sort=sort)
    arguments = {
        "work_id": work_id,
        "output_path": output_path,
        "filename": filename
    }
    # Remove None values
    arguments = {k: v for k, v in arguments.items() if v is not None}

    async with client:
        result = await download_paper(client, arguments)
        return result[0].text if result else "Download failed"

@mcp.tool(name="Compoid_upload_file")
async def Compoid_upload_file(
    file_data: str,
    filename: str = None
) -> str:
    """Upload a file to the Compoid MCP server. Accepts a data URI (data:<mime>;base64,<data>).
    Returns the server-side path to use as file_upload in Compoid_create_record or Compoid_update_record."""
    setup_user_keys_from_headers()
    arguments = {"file_data": file_data}
    if filename:
        arguments["filename"] = filename
    result = await upload_file(arguments)
    return result[0].text if result else "Upload failed"


@mcp.tool(name="Compoid_create_record")
async def Compoid_create_record(
    community_id: str,
    file_upload: str,
    creators: list[str],
    keywords: list[str] = None,
    references: list[str] = None,
    title: str = None,
    description: str = None,
    resource_type: str = None
) -> str:
    """Create a new Compoid record (images, videos, papers, articles, analysis)."""
    setup_user_keys_from_headers()
    client = CompoidClient(sort=sort)
    arguments = {
        "community_id": community_id,
        "file_upload": file_upload,
        "title": title,
        "description": description,
        "creators": creators,
        "keywords": keywords,
        "references": references,
        "resource_type": resource_type
    }
    # Remove None values
    arguments = {k: v for k, v in arguments.items() if v is not None}

    async with client:
        result = await create_record(client, arguments)
        return result[0].text if result else "Failed to create record"

@mcp.tool(name="Compoid_update_record")
async def Compoid_update_record(
    work_id: str,
    file_upload: str = None,
    title: str = None,
    description: str = None,
    creators: list[str] = None,
    keywords: list[str] = None,
    references: list[str] = None,
    resource_type: str = None
) -> str:
    """Update an existing Compoid record. Can update metadata only or replace both file and metadata."""
    setup_user_keys_from_headers()
    client = CompoidClient(sort=sort)
    arguments = {
        "work_id": work_id,
        "file_upload": file_upload,
        "title": title,
        "description": description,
        "creators": creators,
        "keywords": keywords,
        "references": references,
        "resource_type": resource_type
    }
    # Remove None values
    arguments = {k: v for k, v in arguments.items() if v is not None}

    async with client:
        result = await update_record(client, arguments)
        return result[0].text if result else "Failed to update record"

@mcp.tool(name="Compoid_create_community")
async def Compoid_create_community(
    slug: str,
    title: str,
    description: str = None,
    community_type: str = None,
    curation_policy: str = None,
    website: str = None,
    visibility: str = "public",
    member_policy: str = "open",
    record_policy: str = "open",
) -> str:
    """Create a new community on Compoid."""
    setup_user_keys_from_headers()
    client = CompoidClient(sort=sort)
    arguments = {
        "slug": slug,
        "title": title,
        "description": description,
        "community_type": community_type,
        "curation_policy": curation_policy,
        "website": website,
        "visibility": visibility,
        "member_policy": member_policy,
        "record_policy": record_policy,
    }
    # Remove None values
    arguments = {k: v for k, v in arguments.items() if v is not None}

    async with client:
        result = await create_community(client, arguments)
        return result[0].text if result else "Failed to create community"


@mcp.tool(name="Compoid_update_community")
async def Compoid_update_community(
    community_id: str,
    slug: str = None,
    title: str = None,
    description: str = None,
    community_type: str = None,
    curation_policy: str = None,
    website: str = None,
    visibility: str = None,
    member_policy: str = None,
    record_policy: str = None,
) -> str:
    """Update an existing community on Compoid. Only supply the fields you want to change."""
    setup_user_keys_from_headers()
    client = CompoidClient(sort=sort)
    arguments = {
        "community_id": community_id,
        "slug": slug,
        "title": title,
        "description": description,
        "community_type": community_type,
        "curation_policy": curation_policy,
        "website": website,
        "visibility": visibility,
        "member_policy": member_policy,
        "record_policy": record_policy,
    }
    # Remove None values
    arguments = {k: v for k, v in arguments.items() if v is not None}

    async with client:
        result = await update_community(client, arguments)
        return result[0].text if result else "Failed to update community"


def main():
    """Run the MCP server."""
    # Default to stdio for development/testing
    # For HTTP server with headers, use streamable_http_app() mounted in Starlette/FastAPI
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
