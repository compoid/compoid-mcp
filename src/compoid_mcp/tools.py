"""MCP tools for Compoid API interactions."""

import os
import re
import zipfile
from typing import Any, Dict, List

from mcp.types import TextContent, Tool

import base64
import httpx

from compoid_mcp.client import CompoidClient
from compoid_mcp.config import config

def format_work_summary(work: Dict[str, Any]) -> str:
    """Format a work into a readable summary."""
    title = work.get("metadata", {}).get("title", 'N/A')
    authors = []
    for authorship in work.get("metadata", {}).get("creators", []):
        if author := authorship.get("person_or_org"):
            if name := author.get("name"):
                authors.append(name)

    authors_str = ", ".join(authors[:10])  # Limit to first 10 authors
    if len(work.get("metadata", {}).get("creators", [])) > 10:
        authors_str += " +"

    keywords = []
    for contributors_keywords in work.get("metadata", {}).get("contributors", []):
        if keyword := contributors_keywords.get("person_or_org"):
            if name := keyword.get("name"):
                keywords.append(name)

    keywords_str = ", ".join(keywords[:20])  # Limit to first 20 contributors & keywords
    if len(work.get("metadata", {}).get("contributors", [])) > 20:
        keywords_str += " +"

    created = work.get("metadata", {}).get("publication_date", 'N/A')
    updated = work.get("updated", 0)
    main_description = work.get("metadata", {}).get("description", 'N/A')
    main_community = work.get("parent", {}).get("communities", {}).get("default", 'N/A')

    # Get additional_descriptions
    descriptions = []
    for description in work.get("metadata", {}).get("additional_descriptions", [])[:5]:  # First 5 additional_descriptions
        if description_name := description.get("description"):
            descriptions.append(description_name)

    descriptions_str = ", ".join(descriptions) if descriptions else "N/A"

    url = work.get("links", {}).get("self_html", 'N/A')
    image = work.get("files", {}).get("default_preview", 'N/A')
    id = work.get('id', 'N/A')

    # Get topics
    topics = []
    for topic in work.get("metadata", {}).get("subjects", [])[:5]:  # First 5 topics
        if topic_name := topic.get("subject"):
            topics.append(topic_name)

    topics_str = ", ".join(topics) if topics else "No topics"

    # Get communities
    communities = []
    for community in work.get("parent", {}).get("communities", {}).get("entries", [])[:5]:  # First 5 communities
        if community_name := community.get("metadata").get("title"):
            communities.append(community_name)
        if community_id := community.get("id"):
            communities.append(community_id)
    communities_str = ", ".join(communities) if communities else "No community names"

    # Get related identifiers
    identifiers	 = []
    for identifier in work.get("metadata", {}).get("related_identifiers", [])[:5]:  # First 5 identifiers
        if identifier_name := identifier.get("identifier"):
            identifiers.append(identifier_name)

    identifiers_str = ", ".join(identifiers) if identifiers else "N/A"

    # Get references
    references	 = []
    for reference in work.get("metadata", {}).get("references", [])[:5]:  # First 5 identifiers
        if reference_name := reference.get("reference"):
            references.append(reference_name)

    references_str = ", ".join(references) if references else "N/A"

    return (
        f"**{title}**\n"
        f"Authors: {authors_str}\n"
        f"Contributors & Keywords: {keywords_str}\n"
        f"Created: {created} | Updated: {updated}\n"
        f"Description: {main_description}\n"
        f"Additional descriptions: {descriptions_str}\n"
        f"Record URL: {url}\n"
        f"Topics: {topics_str}\n"
        f"Default community ID: {main_community}\n"
        f"Communities: {communities_str}\n"
        f"Related works: {identifiers_str}\n"
        f"References: {references_str}\n"
        f"Record ID: {id}\n"
        f"Image URL: 'https://www.compoid.com/api/iiif/record:{id}:{image}/full/!1024,1024/0/default.png'\n"
    )

def format_community_summary(community: Dict[str, Any]) -> str:
    """Format an community into a readable summary."""
    name =  community.get("metadata", {}).get("title", 'N/A')

    created = community.get("created", 0)
    updated = community.get("updated", 0)
    description = community.get("metadata", {}).get("description", 'N/A')
    url = community.get("links", {}).get("self_html", 'N/A')
    community_records_url = community.get("links", {}).get("records", 'N/A')
    id = community.get('id', 'N/A')
    website = community.get("metadata", {}).get("website", 'N/A')

    return (
        f"**{name}**\n"
        f"Created: {created} | Updated: {updated}\n"
        f"Description: {description}\n"
        f"Community URL: {url}\n"
        f"Community ID: {id}\n"
        f"Community records URL: {community_records_url}\n"
        f"Community website URL: {website}\n"
    )

# Tool definitions
SEARCH_WORKS_TOOL = Tool(
    name="Compoid_search_records",
    description="Search for records (images, videos, papers, articles, analysis) in Compoid",
    inputSchema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query for records (title, description)"
            },
            "title": {
                "type": "string",
                "description": "Search records titles"
            },
            "description": {
                "type": "string",
                "description": "Search records description"
            },
            "community": {
                "type": "string",
                "description": "Search by community"
            },
            "keywords": {
                "type": "string",
                "description": "Search by keywords"
            },
            "creators": {
                "type": "string",
                "description": "Search by Author or AI-Model"
            },
            "date_from": {
                "type": "string",
                "description": "Filter records from this date, format YYYY-MM-DD"
            },
            "date_to": {
                "type": "string",
                "description": "Filter records up to this date, format YYYY-MM-DD"
            },
            "exact_date": {
                "type": "string",
                "description": "Filter by record exact date, format YYYY-MM-DD"
            },
            "access_status": {
                "type": "string",
                "enum": ["open", "restricted"],
                "description": "Filter by record access status"
            },
            "resource_type": {
                "type": "string",
                "enum": ["image", "publication", "video", "dataset", "audio", "presentation", "other", "quantitativeanalysis", "technicalanalysis", "fundamentalanalysis", "software", "workflow", "model", "lesson", "tutorial", "aimodel", "llm", "vlm", "quantmodel", "aiagent"],
                "description": "Filter records by resource type"
            },
            "file_type": {
                "type": "string",
                "enum": ["jpg", "png", "gif", "pdf", "docx", "xlsx", "csv", "json", "xml", "zip", "txt", ".md", ".mkv", ".mp4", ".avi"],
                "description": "Filter records by file type"
            },
            "sort": {
                "type": "string",
                "enum": ["bestmatch", "newest", "oldest", "updated-asc", "updated-desc", "version"],
                "description": "Sort search results. Built-in options are 'bestmatch', 'newest', 'oldest', 'updated-desc', 'updated-asc', 'version' (default: 'bestmatch' or 'newest')."
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "default": 5,
                "description": "Number of results to return (max 50)"
            }
        },
        "required": ["query"]
    }
)


SEARCH_COMMUNITIES_TOOL = Tool(
    name="Compoid_search_communities",
    description="Search for communities in Compoid",
    inputSchema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query for community names"
            },
            "title": {
                "type": "string",
                "description": "Search records titles"
            },
            "description": {
                "type": "string",
                "description": "Search records description"
            },
            "access_status": {
                "type": "string",
                "enum": ["open", "restricted"],
                "description": "Filter by record access status"
            },
            "sort": {
                "type": "string",
                "enum": ["bestmatch", "newest", "oldest", "updated-asc", "updated-desc", "version"],
                "description": "Sort search results. Built-in options are 'bestmatch', 'newest', 'oldest', 'updated-desc', 'updated-asc', 'version' (default: 'bestmatch' or 'newest')."
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 30,
                "default": 5,
                "description": "Number of results to return (max 30)"
            }
        },
        "required": ["query"]
    }
)

GET_WORK_DETAILS_TOOL = Tool(
    name="Compoid_get_record_details",
    description="Get detailed information about a specific record by its Compoid ID or OAI",
    inputSchema={
        "type": "object",
        "properties": {
            "work_id": {
                "type": "string",
                "description": "Compoid record ID (e.g., '4171t-rc787') or OAI"
            }
        },
        "required": ["work_id"]
    }
)

GET_COMMUNITY_DETAILS_TOOL = Tool(
    name="Compoid_get_community_details",
    description="Get detailed information about a specific community by its ID",
    inputSchema={
        "type": "object",
        "properties": {
            "community_id": {
                "type": "string",
                "description": "Compoid community ID (e.g., 'f1658ee7-0c55-4839-8b24-ebaf56d3dff9')"
            }
        },
        "required": ["community_id"]
    }
)

DOWNLOAD_PAPER_TOOL = Tool(
    name="Compoid_download_files",
    description="Download a file if available through open access",
    inputSchema={
        "type": "object",
        "properties": {
            "work_id": {
                "type": "string",
                "description": "Compoid record ID (e.g., '4171t-rc787') or OAI of the record to download"
            },
            "output_path": {
                "type": "string",
                "description": "Directory path where to save the file (optional, defaults to '~/Downloads')"
            },
            "filename": {
                "type": "string",
                "description": "Custom filename (optional, auto-generated if not provided)"
            }
        },
        "required": ["work_id"]
    }
)

CREATE_RECORD_TOOL = Tool(
    name="Compoid_create_record",
    description="Create a new Compoid record (images, videos, papers, articles, analysis).",
    inputSchema={
        "type": "object",
        "properties": {
            "community_id": {
                "type": "string",
                "description": "Compoid community ID (e.g., 'f1658ee7-0c55-4839-8b24-ebaf56d3dff9')"
            },
            "file_upload": {
                "type": "string",
                "description": "File to upload from local path"
            },
            "creators": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "Array of Authors or AI-Models associated with the record (required)"
            },
            "keywords": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "Array of keywords or tags associated with the record (optional)"
            },
            "title": {
                "type": "string",
                "description": "Record title"
            },
            "description": {
                "type": "string",
                "description": "Record description"
            },
            "references": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "Array of references, URLs, or citations (optional)"
            },
            "resource_type": {
                "type": "string",
                "enum": ["image", "video", "audio", "publication", "dataset", "presentation", "quantitativeanalysis", "technicalanalysis", "fundamentalanalysis", "software", "model", "aimodel", "mcp", "sector", "quantmodel", "aiagent", "workflow", "lesson", "tutorial", "other"],
                "description": "Record resource type, the default is image"
            },
        },
        "required": ["file_upload", "community_id", "creators"]
    }
)

UPDATE_RECORD_TOOL = Tool(
    name="Compoid_update_record",
    description="Update an existing Compoid record. Can update metadata only or replace the file and metadata.",
    inputSchema={
        "type": "object",
        "properties": {
            "work_id": {
                "type": "string",
                "description": "Compoid record ID (e.g., '4171t-rc787') or OAI of the record to update (required)"
            },
            "file_upload": {
                "type": "string",
                "description": "File to upload from local path (optional - only needed if replacing the file)"
            },
            "creators": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "Array of Authors or AI-Models associated with the record (optional)"
            },
            "keywords": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "Array of keywords or tags associated with the record (optional)"
            },
            "title": {
                "type": "string",
                "description": "Record title (optional)"
            },
            "description": {
                "type": "string",
                "description": "Record description (optional)"
            },
            "references": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "Array of references, URLs, or citations (optional)"
            },
            "resource_type": {
                "type": "string",
                "enum": ["image", "video", "audio", "publication", "dataset", "presentation", "quantitativeanalysis", "technicalanalysis", "fundamentalanalysis", "software", "model", "aimodel", "mcp", "sector", "quantmodel", "aiagent", "workflow", "lesson", "tutorial", "other"],
                "description": "Record resource type (optional)"
            },
        },
        "required": ["work_id"]
    }
)

UPLOAD_FILE_TOOL = Tool(
    name="Compoid_upload_file",
    description=(
        "Upload a file from the client to the Compoid MCP server. "
        "Accepts a data URI (data:<mime>;base64,<data>) and an optional filename. "
        "Returns the server-side path that can be passed directly to "
        "Compoid_create_record or Compoid_update_record as file_upload."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "file_data": {
                "type": "string",
                "description": (
                    "File content as a data URI: data:<mime-type>;base64,<base64-encoded-data>. "
                    "Example: data:image/png;base64,iVBORw0KGgo..."
                )
            },
            "filename": {
                "type": "string",
                "description": "Original filename including extension (e.g. photo.png). Optional — used to preserve the extension."
            }
        },
        "required": ["file_data"]
    }
)

async def search_records(client: CompoidClient, arguments: Dict[str, Any]) -> List[TextContent]:
    """Search Compoid records."""
    query = arguments["query"]
    community_id = arguments.get("community_id", None)
    limit = arguments.get("limit", 5)
    sort = arguments.get("sort")  # No default sort - let Compoid use relevance

    # Filter out invalid sort values for records
    if sort == "version":
        sort = None  # Use default relevance instead

    filter_title = {}
    if title := arguments.get("title"):
        filter_title["metadata.title"] = title

    filter_description = {}
    if description := arguments.get("description"):
        filter_description["metadata.description"] = description

    filter_community = {}
    if community := arguments.get("community"):
        filter_community["parent.communities.entries.metadata.title"] = community

    filter_keywords = {}
    if keywords := arguments.get("keywords"):
        filter_keywords["metadata.contributors.person_or_org.name"] = keywords

    filter_creators = {}
    if creators := arguments.get("creators"):
        filter_creators["metadata.creators.person_or_org.name"] = creators

    filter_exact_date = {}
    if exact_date := arguments.get("exact_date"):
        filter_exact_date["metadata.publication_date"] = exact_date

    filter_access_status = {}
    if access_status := arguments.get("access_status"):
        filter_access_status["access.status"] = access_status

    filter_resource_type = {}
    if resource_type := arguments.get("resource_type"):
        filter_resource_type["metadata.resource_type.id"] = resource_type

    filter_file_type = {}
    if file_type := arguments.get("file_type"):
        filter_file_type["files.entries.ext"] = file_type

    try:
        response = await client.get_works(
            search=query,
            community_id=community_id,
            filter_title=filter_title,
            filter_description=filter_description,
            filter_community=filter_community,
            filter_keywords=filter_keywords,
            filter_creators=filter_creators,
            filter_exact_date=filter_exact_date,
            filter_access_status=filter_access_status,
            filter_resource_type=filter_resource_type,
            filter_file_type=filter_file_type,
            sort=sort,
            size=limit
        )

        results = response.get("hits", {}).get("hits", [])
        meta = response.get("hits", {})

        if not results:
            return [TextContent(
                type="text",
                text=f"No records found for query: '{query}'"
            )]

        # Format results
        content = f"Found {meta.get('total', len(results))} records for '{query}':\n\n"

        for i, work in enumerate(results, 1):
            content += f"{i}. {format_work_summary(work)}\n"

        return [TextContent(type="text", text=content)]

    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error searching records: {str(e)}"
        )]

async def search_communities(client: CompoidClient, arguments: Dict[str, Any]) -> List[TextContent]:
    """Search for communities in Compoid."""
    query = arguments["query"]
    limit = arguments.get("limit", 1)
    sort = arguments.get("sort")

    filter_title = {}
    if title := arguments.get("title"):
        filter_title["metadata.title"] = title

    filter_description = {}
    if description := arguments.get("description"):
        filter_description["metadata.description"] = description

    filter_access_status = {}
    if access_status := arguments.get("access_status"):
        filter_access_status["access.visibility"] = access_status

    try:
        response = await client.get_communities(
            search=query,
            filter_title=filter_title,
            filter_description=filter_description,
            filter_access_status=filter_access_status,
            sort=sort,
            size=limit
        )

        results = response.get("hits", {}).get("hits", [])
        meta = response.get("hits", {})

        if not results:
            return [TextContent(
                type="text",
                text=f"No communities found for query: '{query}'"
            )]

        # Format results
        content = f"Found {meta.get('count', len(results))} communities for '{query}':\n\n"

        for i, community in enumerate(results, 1):
            content += f"{i}. {format_community_summary(community)}\n"

        return [TextContent(type="text", text=content)]

    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error searching communities: {str(e)}"
        )]

async def get_work_details(client: CompoidClient, arguments: Dict[str, Any]) -> List[TextContent]:
    """Get detailed information about a specific record."""
    work_id = arguments["work_id"]
    original_id = work_id  # Keep for error messages

    # Extract record ID oai
    if work_id.startswith("oai:www.compoid.com"):
        work_id = work_id.split(":")[-1]  # Extract just the ID
    # Handle hull_html format
    elif work_id.startswith("https://www.compoid.com/records"):
        work_id = work_id.split("/")[-1]  # Extract just the ID

    try:
        response = await client.get_works(work_id=work_id)

        if not response:
            return [TextContent(
                type="text",
                text=f"Work not found: {original_id}"
            )]

        work = response

        access_status = work.get("access", {}).get("status")

        # Format detailed work information
        content = format_work_summary(work)

        # Add additional details
        if oai := work.get("pids", {}).get("oai"):
            content += f"OAI: {oai}\n"

        if access_status == "open":
            content += "Open Access: Yes\n"
            if best_oa := work.get("links"):
                if archive_url := best_oa.get("archive"):
                    content += f"File URL: {archive_url}\n"

        return [TextContent(type="text", text=content)]

    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error getting record details: {str(e)}"
        )]

async def get_community_details(client: CompoidClient, arguments: Dict[str, Any]) -> List[TextContent]:
    """Get detailed information about a specific record."""
    community_id = arguments["community_id"]
    original_id = community_id  # Keep for error messages

    try:
        response = await client.get_communities(community_id=community_id)

        if not response:
            return [TextContent(
                type="text",
                text=f"Community not found: {original_id}"
            )]

        community = response

        access_status = community.get("access", {}).get("visibility")

        # Format detailed community information
        content = format_community_summary(community)

        # Add additional details
        if oai := community.get("pids", {}).get("oai"):
            content += f"OAI: {oai}\n"

        if access_status == "open":
            content += "Open Access: Yes\n"
            if best_oa := community.get("links"):
                if archive_url := best_oa.get("archive"):
                    content += f"File URL: {archive_url}\n"

        return [TextContent(type="text", text=content)]

    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error getting record details: {str(e)}\n"
                 f"Check if the community_id {community_id} is correct and if the community exists."
        )]

async def download_paper(client: CompoidClient, arguments: Dict[str, Any]) -> List[TextContent]:
    """Download a paper's PDF if available through open access."""
    work_id = arguments["work_id"]
    if arguments.get("output_path").startswith(config.download_path):
        directory_path = "/" + arguments.get("output_path").split("/")[-1]  # Extract just the directory path
    elif arguments.get("output_path").startswith("~"):
        directory_path = arguments.get("output_path").split("~")[-1] # Extract just the directory path
    elif arguments.get("output_path") == "/":
        directory_path = "/" + work_id
    elif arguments.get("output_path").startswith("/"):
        directory_path = arguments.get("output_path")
    else:
        directory_path = "/" + arguments.get("output_path")
    output_path = os.path.expanduser(config.download_path + directory_path)

    # Extract record ID from oai
    if work_id.startswith("oai:www.compoid.com"):
        work_id = work_id.split(":")[-1]  # Extract just the ID
    # Handle hull_html format
    elif work_id.startswith("https://www.compoid.com/records"):
        work_id = work_id.split("/")[-1]  # Extract just the ID

    try:
        # First get the work details to find PDF URL
        response = await client.get_works(work_id=work_id)

        if not response:
            return [TextContent(
                type="text",
                text=f"Record not found: {work_id}"
            )]

        work = response
        title = work.get("id") or work.get("metadata", {}).get("title", "Unknown Title")
        
        access_status = work.get("access", {}).get("status")

        # Check if paper has open access PDF
        archive_url = None
        if access_status == "open":
            if best_oa := work.get("links"):
                if archive_url := best_oa.get("archive"):
                    archive_url = work.get("links", {}).get("archive")

        if not archive_url:
            return [TextContent(
                type="text",
                text=f"No open access files available for: {title}\n"
                     f"The files may be behind a paywall or not available."
            )]

        # Generate filename if not provided
        if arguments.get("filename"):
            custom_filename =  arguments.get("filename") + ".zip"
        else:
            # Clean title for filename
            clean_title = re.sub(r'[<>:"/\\|?*]', '', title)
            clean_title = clean_title.replace(' ', '_')[:50]  # Limit length
            custom_filename = f"{clean_title}.zip"

        # Ensure output directory exists and is writable
        try:
            os.makedirs(output_path, exist_ok=True)
            # Test if directory is writable
            test_file = os.path.join(output_path, ".write_test")
            try:
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
            except (OSError, PermissionError):
                # Fallback to home directory if Downloads is not writable
                output_path = os.path.expanduser("~")
                os.makedirs(output_path, exist_ok=True)
        except (OSError, PermissionError) as e:
            return [TextContent(
                type="text",
                text=f"Cannot create or write to directory: {output_path}\n"
                     f"Error: {str(e)}\n"
                     f"Please specify a writable output_path parameter."
            )]

        # Full file path
        file_path = os.path.join(output_path, custom_filename)

        # Download the PDF
        success = await client.download_pdf(archive_url, file_path)

        if success:
            # Get file size for confirmation
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
            extracted_files = 'N/A'
            if config.extract_archive:
                extracted_files = zipfile.ZipFile(file_path).namelist()
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(output_path)

            return [TextContent(
                type="text",
                text=f"Successfully downloaded: {title}\n"
                     f"Downloaded archive: {file_path}\n"
                     f"Extract archive: {config.extract_archive}\n"
                     f"Extracted files: {extracted_files}\n"
                     f"Size: {file_size_mb:.2f} MB\n"
                     f"Source: {archive_url}"
            )]
        else:
            return [TextContent(
                type="text",
                text=f"Failed to download files archive for: {title}\n"
                     f"URL: {archive_url}\n"
                     f"Check logs for detailed error information."
            )]

    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error downloading record files: {str(e)}"
        )]


async def upload_file(arguments: Dict[str, Any]) -> List[TextContent]:
    """Upload a file (data URI) to the server via the upload server, return server path."""
    file_data = arguments["file_data"]
    filename = arguments.get("filename", "")

    # Parse data URI: data:<mime>;base64,<data>
    if not file_data.startswith("data:"):
        return [TextContent(
            type="text",
            text="Invalid file_data: must be a data URI starting with 'data:'"
        )]

    try:
        # Split header from base64 payload: data:<mime>;base64,<data>
        header, b64_data = file_data.split(",", 1)
        # Extract MIME type from header (e.g. "data:text/markdown;base64" → "text/markdown")
        mime_type = header.split(":")[1].split(";")[0].strip() if ":" in header else "application/octet-stream"
        raw_bytes = base64.b64decode(b64_data)
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Failed to decode file_data: {str(e)}"
        )]

    # Build headers for the upload request
    headers: Dict[str, str] = {
        "Content-Type": mime_type,
    }
    if filename:
        headers["X-Filename"] = filename
    # Forward the mcp-proxy Bearer token to authenticate with the upload server
    # config.proxy_token is extracted from the Authorization header on each request
    if config.proxy_token:
        headers["Authorization"] = f"Bearer {config.proxy_token}"

    with open('mcp_headers.txt', 'w') as wfile:
        wfile.write("headers: {}\n".format(headers))
 
    try:
        async with httpx.AsyncClient(timeout=120.0) as http:
            response = await http.post(
                config.upload_server_url,
                content=raw_bytes,
                headers=headers
            )
            response.raise_for_status()
            result = response.json()
    except httpx.HTTPStatusError as e:
        return [TextContent(
            type="text",
            text=f"Upload server returned error {e.response.status_code}: {e.response.text}"
        )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Failed to reach upload server: {str(e)}"
        )]

    server_path = result.get("file_path") or result.get("path")
    size = result.get("size", len(raw_bytes))

    return [TextContent(
        type="text",
        text=f"File uploaded successfully.\n"
             f"Server path: {server_path}\n"
             f"Size: {size} bytes\n\n"
             f"Use this path as file_upload in Compoid_create_record or Compoid_update_record."
    )]


async def create_record(client: CompoidClient, arguments: Dict[str, Any]) -> List[TextContent]:
    """Create new Compoid record."""
    
    file_upload = arguments["file_upload"]
    community_id = arguments["community_id"]
    creators = arguments.get("creators")

    filter_title = None
    if title := arguments.get("title"):
        filter_title = title

    filter_description = None
    if description := arguments.get("description"):
        filter_description = description

    filter_references = None
    if references := arguments.get("references"):
        filter_references = references

    filter_keywords = None
    if keywords := arguments.get("keywords"):
        filter_keywords = keywords

    filter_resource_type = None
    if resource_type := arguments.get("resource_type"):
        filter_resource_type = resource_type

    # Handle file input: Option 3 - Stream large files efficiently via httpx
    # The server cannot access client-local paths, so we stream them via HTTP
    
    if file_upload.startswith("data:"):
        # Data URI format - pass through to client handler as-is
        print(f"Using data URI format")

    elif file_upload.startswith("/projects"):
        # Remote server file - use directly
        print(f"Using remote file: {file_upload}")
    
    else:
        # Local client file - stream it via httpx
        # NOTE: This only works if the file exists on the SERVER (where this code runs)
        # For true client-side files, the MCP client must upload them first
        print(f"Attempting to stream file via httpx: {file_upload}")
        
        # Check if file exists on the server (skip for very long strings that might be base64)
        if len(file_upload) < 500 and not os.path.exists(file_upload):
            return [TextContent(
                type="text",
                text=f"File not found on server: {file_upload}\n\n"
                     f"MCP servers cannot access client-local files directly.\n"
                     f"The file must be uploaded to the server first using one of these methods:\n\n"
                     f"1. Convert to base64 (example.md as markdown mime type): \"file_upload\": \"data:text/markdown;base64,XXXX\",\n"
                     f"2. Upload manually: curl -X POST https://mcps.compoid.com/upload --data-binary @{os.path.basename(file_upload)}\n"
                     f"3. Use a server-side path (starts with /projects/)\n"
                     f"Then use the returned server path as the file_upload parameter."
            )]

    print("Creating new record")
    
    try:
        success = await client.upload_record(community_id=community_id, file_upload=file_upload, creators=creators, filter_title=filter_title, filter_description=filter_description, filter_references=filter_references, filter_keywords=filter_keywords, filter_resource_type=filter_resource_type)
        if success[0] and len(success) == 3:
            created_work_id = success[1]
            draft_url = success[2]
            return [TextContent(
                type="text",
                text=f"Draft request submitted:\n"
                     f"Draft ID: {created_work_id}\n"
                     f"Community ID: {community_id}\n"
                     f"Draft URL: {draft_url}\n"
                     f"Your submission is pending review by the community moderators."
            )]
        elif success[0] and len(success) == 2:
            created_work_id = success[1]
            response = await client.get_works(work_id=created_work_id)
            if not response:
                return [TextContent(
                    type="text",
                    text=f"Record not found: {created_work_id}"
                )]
            work = response
            # Format detailed work information
            content = format_work_summary(work)
            # Add additional details
            if oai := work.get("pids", {}).get("oai"):
                content += f"OAI: {oai}\n"
            # Get file size for confirmation (if file still exists)
            # Skip size check for data URIs and very long strings (likely base64)
            try:
                if len(file_upload) < 500 and not file_upload.startswith("data:"):
                    file_size = os.path.getsize(file_upload)
                    file_size_mb = file_size / (1024 * 1024)
                    size_info = f"Size: {file_size_mb:.2f} MB\n"
                else:
                    size_info = f"Base64: {len(file_upload)}\n"
            except (FileNotFoundError, OSError):
                # File may have been cleaned up (e.g., temp file from base64)
                size_info = ""
            
            return [TextContent(
                type="text",
                text=f"Successfully created record:\n"
                     f"{content}\n"
                     f"Community ID: {community_id}\n"
                     f"Uploaded File: {file_upload}\n"
                     f"{size_info}"
            )]
        else:
            return [TextContent(
                type="text",
                text=f"Failed to create record with parameters:\n"
                     f"Community ID: {community_id}\n"
                     f"File: {file_upload}\n"
                     f"Creators: {creators}\n"
                     f"Title: {filter_title}\n"
                     f"Description: {filter_description}\n"
                     f"Resource Type: {filter_resource_type}"
            )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error creating record: {str(e)}"
        )]


async def update_record(client: CompoidClient, arguments: Dict[str, Any]) -> List[TextContent]:
    """Update existing Compoid record."""
    
    work_id = arguments["work_id"]
    if work_id.startswith("oai:www.compoid.com"):
        work_id = work_id.split(":")[-1]  # Extract just the ID
    elif work_id.startswith("https://www.compoid.com/records"):
        work_id = work_id.split("/")[-1]  # Extract just the ID

    filter_creators = arguments.get("creators")
    filter_file_upload = arguments.get("file_upload")
    filter_title = arguments.get("title")
    filter_description = arguments.get("description")
    filter_references = arguments.get("references")
    filter_keywords = arguments.get("keywords")
    filter_resource_type = arguments.get("resource_type")
   
    # If file_upload is provided, validate it
    if filter_file_upload:
        if filter_file_upload.startswith("data:"):
            print(f"Using data URI format")
        elif filter_file_upload.startswith("/projects"):
            print(f"Using remote file: {filter_file_upload}")
        else:
            print(f"Attempting to stream file via httpx: {filter_file_upload}")
            if len(filter_file_upload) < 500 and not os.path.exists(filter_file_upload):
                return [TextContent(
                    type="text",
                    text=f"File not found on server: {filter_file_upload}\n\n"
                         f"MCP servers cannot access client-local files directly.\n"
                         f"The file must be uploaded to the server first using one of these methods:\n\n"
                         f"1. Convert to base64 (example.md as markdown mime type): \"file_upload\": \"data:text/markdown;base64,XXXX\",\n"
                         f"2. Upload manually: curl -X POST https://mcps.compoid.com/upload --data-binary @{os.path.basename(filter_file_upload)}\n"
                         f"3. Use a server-side path (starts with /projects/)\n"
                         f"Then use the returned server path as the file_upload parameter."
                )]
    else:
        print(f"Updating metadata only for record {work_id}")
    
    try:
        success = await client.modify_record(
            work_id=work_id,
            file_upload=filter_file_upload,
            filter_creators=filter_creators,
            filter_title=filter_title,
            filter_description=filter_description,
            filter_references=filter_references,
            filter_keywords=filter_keywords,
            filter_resource_type=filter_resource_type
        )
        if success[0]:
            updated_work_id = success[1]
            response = await client.get_works(work_id=updated_work_id)
            if not response:
                return [TextContent(
                    type="text",
                    text=f"Record not found: {updated_work_id}"
                )]
            work = response
            # Format detailed work information
            content = format_work_summary(work)
            # Add additional details
            if oai := work.get("pids", {}).get("oai"):
                content += f"OAI: {oai}\n"
            
            file_info = f"Updated File: {filter_file_upload}\n" if filter_file_upload else "Metadata-only update\n"
            
            return [TextContent(
                type="text",
                text=f"Successfully updated record:\n"
                     f"{content}\n"
                     f"{file_info}"
            )]
        else:
            return [TextContent(
                type="text",
                text=f"Failed to update record {work_id}"
            )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error updating record: {str(e)}"
        )]


CREATE_COMMUNITY_TOOL = Tool(
    name="Compoid_create_community",
    description="Create a new community on Compoid.",
    inputSchema={
        "type": "object",
        "properties": {
            "slug": {
                "type": "string",
                "description": "URL-compatible identifier for the community (max 100 chars, e.g. 'my-community'). Required."
            },
            "title": {
                "type": "string",
                "description": "Human-readable title of the community (max 250 chars). Required."
            },
            "description": {
                "type": "string",
                "description": "Short description of the community (optional, max 2000 chars)."
            },
            "community_type": {
                "type": "string",
                "description": "Community type id, e.g. 'repository', 'workspace', 'finanalysis' (optional)."
            },
            "curation_policy": {
                "type": "string",
                "description": "Description of how records are curated (optional, HTML allowed)."
            },
            "website": {
                "type": "string",
                "description": "URL to an external website for this community (optional)."
            },
            "visibility": {
                "type": "string",
                "enum": ["public", "restricted"],
                "description": "Visibility of the community (default: 'public')."
            },
            "member_policy": {
                "type": "string",
                "enum": ["open", "closed"],
                "description": "Whether people can request membership (default: 'open')."
            },
            "record_policy": {
                "type": "string",
                "enum": ["open", "closed"],
                "description": "Whether members can submit records without review (default: 'open')."
            }
        },
        "required": ["slug", "title"]
    }
)

UPDATE_COMMUNITY_TOOL = Tool(
    name="Compoid_update_community",
    description="Update an existing community on Compoid. Fetches the current community and merges the supplied fields.",
    inputSchema={
        "type": "object",
        "properties": {
            "community_id": {
                "type": "string",
                "description": "UUID or slug of the community to update (required)."
            },
            "slug": {
                "type": "string",
                "description": "New URL-compatible slug (optional)."
            },
            "title": {
                "type": "string",
                "description": "New human-readable title (optional)."
            },
            "description": {
                "type": "string",
                "description": "New short description (optional)."
            },
            "community_type": {
                "type": "string",
                "description": "New community type id, e.g. 'repository', 'workspace' (optional)."
            },
            "curation_policy": {
                "type": "string",
                "description": "New curation policy text (optional)."
            },
            "website": {
                "type": "string",
                "description": "New external website URL (optional)."
            },
            "visibility": {
                "type": "string",
                "enum": ["public", "restricted"],
                "description": "New visibility setting (optional)."
            },
            "member_policy": {
                "type": "string",
                "enum": ["open", "closed"],
                "description": "New member policy (optional)."
            },
            "record_policy": {
                "type": "string",
                "enum": ["open", "closed"],
                "description": "New record submission policy (optional)."
            }
        },
        "required": ["community_id"]
    }
)


async def create_community(client: CompoidClient, arguments: Dict[str, Any]) -> List[TextContent]:
    """Create a new Compoid community."""
    slug = arguments["slug"]
    title = arguments["title"]
    try:
        community = await client.create_community(
            slug=slug,
            title=title,
            description=arguments.get("description"),
            community_type=arguments.get("community_type"),
            curation_policy=arguments.get("curation_policy"),
            website=arguments.get("website"),
            visibility=arguments.get("visibility", "public"),
            member_policy=arguments.get("member_policy", "open"),
            record_policy=arguments.get("record_policy", "open"),
        )
        summary = format_community_summary(community)
        return [TextContent(
            type="text",
            text=f"Successfully created community:\n{summary}"
        )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error creating community: {str(e)}"
        )]


async def update_community(client: CompoidClient, arguments: Dict[str, Any]) -> List[TextContent]:
    """Update an existing Compoid community."""
    community_id = arguments["community_id"]
    try:
        community = await client.update_community(
            community_id=community_id,
            slug=arguments.get("slug"),
            title=arguments.get("title"),
            description=arguments.get("description"),
            community_type=arguments.get("community_type"),
            curation_policy=arguments.get("curation_policy"),
            website=arguments.get("website"),
            visibility=arguments.get("visibility"),
            member_policy=arguments.get("member_policy"),
            record_policy=arguments.get("record_policy"),
        )
        summary = format_community_summary(community)
        return [TextContent(
            type="text",
            text=f"Successfully updated community:\n{summary}"
        )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error updating community: {str(e)}"
        )]
