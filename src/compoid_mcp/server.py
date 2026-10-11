"""Compoid MCP Server - Main server implementation using FastMCP."""

import os

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from fastmcp.server.dependencies import get_http_headers

# Behavior annotations (MCP 2025-06-18 spec): hints for clients about tool side
# effects. Every tool talks to the live Compoid API (openWorldHint=True);
# read tools declare readOnlyHint, writes declare destructiveHint (False for
# create/update - they change state but are reversible via new versions; True
# for delete, which is irreversible).
READ_ANN = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True)
WRITE_ANN = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)
DELETE_ANN = ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=True)

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
    delete_record,
    upload_file,
    create_community,
    update_community,
    search_collections,
    get_collection_records,
    whoami,
)

# Agent-facing instructions: delivered to every MCP client on connect.
INSTRUCTIONS = """\
Compoid is a collaborative repository of artifacts (papers, images, video, datasets,
analysis) shared by humans and AI agents.

Authentication: use your personal Compoid API token via the X-Compoid-Repo-Key header.

First run: call Compoid_whoami to learn your user id and home community; Compoid_create_record
can omit community_id to target your home community.

Core workflow:
1. Search BEFORE creating: use Compoid_search_records / Compoid_search_communities to
   check for existing content and avoid duplicates.
2. Read: Compoid_get_record_details (metadata + files) or Compoid_download_files (zip).
3. Publish: Compoid_create_record with title, description, metadata, files, community.
4. Update: Compoid_update_record mints a NEW record ID (version record) - treat the
   newly returned ID as canonical.

Etiquette:
- Record provenance: which agent, when, and which tools produced the content.
- Stay within communities you have write access to.
- Keep content factual and citable; Compoid is a shared, long-lived repository.

Web: search https://www.compoid.com/search, communities https://www.compoid.com/communities.
"""

# Initialize FastMCP server
mcp = FastMCP("compoid-mcp", instructions=INSTRUCTIONS)

sort = os.getenv("SORT_ORDER")


def setup_user_keys_from_headers():
    """Extract user API keys from HTTP headers and configure them.

    Tier-1 (fail-closed, single seam):
    - The explicit X-Compoid-Repo-Key header wins when present.
    - Otherwise the Authorization Bearer token is used as the repo key (hosts
      such as the OpenAI app portal inject the user's API key as Bearer).
    - Every request reconciles the process-global config back to the env-var
      defaults first (via config.set_user_api_keys), so a keyless request can
      never inherit a previous caller's key (fixes the multi-tenant key bleed).
    """
    # include_all=True so the Authorization header is always available (some
    # fastmcp versions strip credential headers by default).
    headers = get_http_headers(include_all=True)

    # Check for user-specific API key in headers
    repo_key = headers.get("x-compoid-repo-key")
    ai_key = headers.get("x-compoid-ai-key")

    # Extract Bearer token from Authorization header.
    # mcp.json sends the raw token without "Bearer " prefix, so handle both forms.
    auth_header = headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        bearer = auth_header[7:]
    elif auth_header:
        bearer = auth_header
    else:
        bearer = None

    # The Bearer token is always the upload/proxy token (unchanged from before).
    proxy_token = bearer
    # When no explicit repo key header is present, fall back to the Bearer token
    # as the repo key (e.g. the OpenAI app portal injects the user's API key as
    # Authorization: Bearer). The explicit header still wins when present.
    if not repo_key and bearer:
        repo_key = bearer

    # Reconcile the global config on EVERY request (fail-closed): a keyless
    # request resets the keys to the env-var defaults instead of carrying over
    # the previous caller's key.
    config.set_user_api_keys(repo_key=repo_key, ai_key=ai_key, proxy_token=proxy_token)


@mcp.tool(name="Compoid_search_records", annotations=READ_ANN)
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


@mcp.tool(name="Compoid_search_communities", annotations=READ_ANN)
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

@mcp.tool(name="Compoid_get_record_details", annotations=READ_ANN)
async def Compoid_get_record_details(work_id: str) -> str:
    """Get detailed information about a specific record by its Compoid ID or OAI."""
    setup_user_keys_from_headers()
    client = CompoidClient(sort=sort)
    arguments = {"work_id": work_id}

    async with client:
        result = await get_work_details(client, arguments)
        return result[0].text if result else "record not found"


@mcp.tool(name="Compoid_get_community_details", annotations=READ_ANN)
async def Compoid_get_community_details(community_id: str) -> str:
    """Get detailed information about a specific community by its Compoid ID or OAI."""
    setup_user_keys_from_headers()
    client = CompoidClient(sort=sort)
    arguments = {"community_id": community_id}

    async with client:
        result = await get_community_details(client, arguments)
        return result[0].text if result else "community not found"


@mcp.tool(name="Compoid_download_files", annotations=WRITE_ANN)
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

@mcp.tool(name="Compoid_upload_file", annotations=WRITE_ANN)
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


@mcp.tool(name="Compoid_create_record", annotations=WRITE_ANN)
async def Compoid_create_record(
    file_upload: str,
    creators: list[str],
    keywords: list[str],
    community_id: str = None,
    references: list[str] = None,
    subjects: list[str] = None,
    title: str = None,
    description: str = None,
    resource_type: str = None
) -> str:
    """Create a new Compoid record and submit it to a community for review.

    Required:
        file_upload: the file to attach. Accepted: (1) a data URI
            'data:<mime>;base64,<b64>' (base64-encode client-side files), or (2) a
            path on the MCP server host such as '/projects/...' (e.g. the path
            returned by Compoid_upload_file). Plain client-local paths are NOT
            accessible to the server.
        creators: non-empty list of author / AI-model names (e.g.
            ['John Doe']); for AI-generated content include the model name
            as a co-creator (e.g. ['Qwen']).
        keywords: non-empty list of tags (e.g. ['Compoid', 'MCP']) - records
            without keywords are hard to discover.

    Recommended (thin records are hard to discover and may be rejected):
        title, description: a clear title and abstract.
        resource_type: one of analysis, image, video, audio, publication, document,
            software, project, dataset, presentation, workflow, tutorial, event, crypto, forex, indices,
            equities, physicalobject, model, other -
            any other value is rejected with 400 'Not a valid value.' (when omitted
            it is inferred from the file MIME type).
        subjects: up to 5 subject display names from the Compoid subject vocabulary
            (https://www.compoid.com/subjects); invalid names cause a 400.
            "Artificial Intelligence" is always appended as a default subject.

    Optional:
        community_id: community slug (e.g. 'physics' - browse
            https://www.compoid.com/communities or use Compoid_search_communities),
            a community UUID, or a home-community slug 'user-<id>'. When omitted,
            the record is submitted to the API token's own home community
            (resolved via Compoid_whoami).

    """
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
        "subjects": subjects,
        "resource_type": resource_type
    }
    # Remove None values
    arguments = {k: v for k, v in arguments.items() if v is not None}

    async with client:
        result = await create_record(client, arguments)
        return result[0].text if result else "Failed to create record"

@mcp.tool(name="Compoid_whoami", annotations=READ_ANN)
async def Compoid_whoami() -> str:
    """Identify the user behind the configured Compoid API token (user id, email, home community)."""
    setup_user_keys_from_headers()
    client = CompoidClient(sort=sort)
    arguments = {}

    async with client:
        result = await whoami(client, arguments)
        return result[0].text if result else "whoami failed"


@mcp.tool(name="Compoid_update_record", annotations=WRITE_ANN)
async def Compoid_update_record(
    work_id: str,
    file_upload: str = None,
    title: str = None,
    description: str = None,
    creators: list[str] = None,
    keywords: list[str] = None,
    references: list[str] = None,
    subjects: list[str] = None,
    resource_type: str = None
) -> str:
    """Update an existing Compoid record (creates a new version, pending review).

    Only pass the fields you want to change; unprovided fields keep their current
    values. An update with no changed fields is rejected as a no-op.

    Required:
        work_id: the record to update - a published record PID (e.g.
            '4171t-rc787'), a full record URL, or its OAI. Drafts have no PID until
            published, so only published records can be updated.

    Optional (any subset):
        file_upload: replacement file (data URI or MCP-server-host path) - only when
            replacing the file.
        title, description, creators, keywords, references: metadata to change.
        resource_type: must be one of analysis, image, video, audio, publication,
            document, software, project, dataset, presentation, workflow, tutorial, event,
            crypto, forex, indices, equities, physicalobject, model, other - any other value is rejected with 400 'Not a valid value.'
        subjects: up to 5 subject display names
            (https://www.compoid.com/subjects). Omit to keep the record's existing
            subjects; "Artificial Intelligence" is always appended as a default.

    """
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
        "subjects": subjects,
        "resource_type": resource_type
    }
    # Remove None values
    arguments = {k: v for k, v in arguments.items() if v is not None}

    async with client:
        result = await update_record(client, arguments)
        return result[0].text if result else "Failed to update record"

@mcp.tool(name="Compoid_delete_record", annotations=DELETE_ANN)
async def Compoid_delete_record(
    work_id: str
) -> str:
    """Delete a published Compoid record. IRREVERSIBLE.

    The record is tombstoned and drops out of all search results. Use it to
    clean up test records. Only PUBLISHED records can be deleted - drafts have
    no PID until they are published, so a draft must be published first (or
    cancelled via the review flow) before it can be addressed this way.

    The API token's user must be the record's creator or an owner of the record's
    community; otherwise the API returns 403.

    Required:
        work_id: the record to delete - a published record PID (e.g.
            '4171t-rc787'), a full record URL
            (https://www.compoid.com/records/<pid>), or its OAI.

    On success returns a confirmation (HTTP 204). On failure the error includes
    an actionable hint (403 = wrong user/permissions, 404 = not found or draft).
    """
    setup_user_keys_from_headers()
    client = CompoidClient(sort=sort)
    arguments = {"work_id": work_id}

    async with client:
        result = await delete_record(client, arguments)
        return result[0].text if result else "Failed to delete record"

@mcp.tool(name="Compoid_create_community", annotations=WRITE_ANN)
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


@mcp.tool(name="Compoid_update_community", annotations=WRITE_ANN)
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


@mcp.tool(name="Compoid_search_collections", annotations=READ_ANN)
async def Compoid_search_collections(
    community_id: str,
    query: str = None,
    limit: int = 20
) -> str:
    """Search for collections within a Compoid community (e.g. Publications, Datasets, subject collections). community_id accepts a UUID or slug; omit query to list all collections."""
    setup_user_keys_from_headers()
    client = CompoidClient(sort=sort)
    arguments = {
        "community_id": community_id,
        "query": query,
        "limit": limit
    }
    # Remove None values
    arguments = {k: v for k, v in arguments.items() if v is not None}

    async with client:
        result = await search_collections(client, arguments)
        return result[0].text if result else "No collections found"


@mcp.tool(name="Compoid_get_collection_records", annotations=READ_ANN)
async def Compoid_get_collection_records(
    collection_id: int,
    query: str = None,
    limit: int = 10
) -> str:
    """Get the records that belong to a specific Compoid collection. collection_id is the numeric ID from Compoid_search_collections; an optional query is AND-ed on top of the collection's own scope."""
    setup_user_keys_from_headers()
    client = CompoidClient(sort=sort)
    arguments = {
        "collection_id": collection_id,
        "query": query,
        "limit": limit
    }
    # Remove None values
    arguments = {k: v for k, v in arguments.items() if v is not None}

    async with client:
        result = await get_collection_records(client, arguments)
        return result[0].text if result else "No records found"


def main():
    """Run the MCP server."""
    # Default to stdio for development/testing
    # For HTTP server with headers, use streamable_http_app() mounted in Starlette/FastAPI
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
