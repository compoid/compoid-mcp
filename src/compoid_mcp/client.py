"""Compoid API client for making HTTP requests to the Compoid API."""

import asyncio
import mimetypes
import os
import string
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
import base64
import tempfile
import subprocess
import httpx
from pathlib import Path

from compoid_mcp.config import config
from compoid_mcp.logutil import logger
## create record
import requests
import json
import re
import time
from datetime import date, timedelta
from jinja2 import Environment, FileSystemLoader

# Templates ship inside the installed package (wheel/sdist); resolve them
# relative to this file rather than the current working directory.
_TEMPLATES_DIR = str(Path(__file__).resolve().parent / "templates")


CLASSIFICATION_MAP = {
    'general': 'public',
    'open_access': 'public',
    'private': 'internal',
    'sensitive': 'confidential',
    'proprietary': 'restricted',
}


# Actionable hints for common API status codes, appended to error messages so
# agents can self-correct without trial and error.
_STATUS_HINTS = {
    400: "Fix the offending request field: enum fields must use valid values "
         "('resource_type' must be one of: analysis, image, video, audio, publication, "
         "document, software, project, dataset, presentation, workflow, tutorial, other; "
         "'subjects' must be display names from https://www.compoid.com/subjects, max 5) and "
         "required fields (creators, keywords) must be non-empty.",
    401: "The API token is missing, invalid, or expired (check the Bearer / repo-key config).",
    403: "Permission denied - the token's user is not a member/owner of this community, or the "
         "record is restricted. For home communities (user-<id>) the token must belong to that user.",
    404: "The record/community/work_id does not exist (note: drafts are not addressable by PID "
         "until published; check the ID for typos).",
    410: "The record has already been deleted (tombstoned) - nothing to do; treat this as a "
         "successful cleanup (deletes are idempotent).",
}


def _hint_for(status_code: int) -> str:
    """Return an actionable hint suffix for an HTTP status code."""
    hint = _STATUS_HINTS.get(status_code)
    return f"\nHint: {hint}" if hint else ""


def classify_content(content_class):
    """Map a VLM content-rating name to a valid v14 classification (id, title).

    Ratings keep their granular labels (Private -> internal, Sensitive ->
    confidential, Proprietary -> restricted); only General/Open Access are
    public. Access restriction is decided separately by the caller via
    ``content_public`` (``content_class_id == 'public'``), so every
    non-public rating yields a restricted record regardless of its label;
    unknown ratings fail closed to ``restricted`` here.
    """
    # The VLM emits "Open Access" (space); the map key is "open_access".
    # Normalise spaces to underscores so every rating hits its real entry.
    key = str(content_class).strip().lower().replace(' ', '_')
    cid = CLASSIFICATION_MAP.get(key, 'restricted')
    return cid, cid.capitalize()


def resolve_community_visibility(community_ref: str):
    """Resolve a community slug or UUID via the API.

    Home communities (``user-<id>``) and any community with
    ``access.visibility == "restricted"`` need records with restricted access;
    publishing a public record into a restricted community fails with
    400 "A public record cannot be included in a restricted community."

    Returns (community_id, is_restricted) where community_id is the canonical
    UUID. On any failure returns (None, False) so callers fall back to the
    existing behavior (dict-based resolution, public access).
    """
    try:
        resp = requests.get(
            f"{config.repo_api_base_url}/communities/{community_ref}",
            headers={"Authorization": f"Bearer {config.repo_api_key}"},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("id"), (data.get("access") or {}).get("visibility") == "restricted"
        logger.warning(f"Community visibility check for {community_ref}: HTTP {resp.status_code}")
    except Exception as e:
        logger.warning(f"Community visibility check failed for {community_ref}: {e}")
    return None, False


# Default subject always appended to every record (mirrors default_reference).
# Subject anchors are the display name with spaces replaced by underscores
# (verified against all live subjects at https://www.compoid.com/subjects).
DEFAULT_SUBJECT = "Artificial Intelligence"
DEFAULT_SUBJECT_MAP = "Artificial_Intelligence"


class CompoidClient:
    """Async client for the Compoid API."""

    def __init__(self, sort: Optional[str] = None, timeout: Optional[float] = None):
        """Initialize the Compoid client.
        
        Args:
            sort: sort address for polite pool access (recommended)
            timeout: Request timeout in seconds
        """
        self.sort = sort or config.sort
        self._timeout = timeout  # Store original value, use property for dynamic config access
        self._client: Optional[httpx.AsyncClient] = None
        self._rate_limiter = asyncio.Semaphore(config.max_concurrent_requests)

    def _is_likely_base64(self, text: str) -> bool:
        """Determine if text is likely base64-encoded content rather than a file path.
        
        Args:
            text: String to check
            
        Returns:
            True if text is likely base64 content, False if likely a file path
        """
        
        # Absolute paths - always treat as file paths
        if text.startswith(("/", "\\")) or (len(text) > 2 and text[1:3] == ":\\"):
            return False
        
        # Relative paths
        if text.startswith((".", "~")):
            return False
        
        # Windows UNC paths
        if text.startswith("\\\\"):
            return False
        
        # Very short strings are probably file paths
        if len(text) < 100:
            return False
        
        # Check for typical file extensions at the end
        common_extensions = (
            '.txt', '.pdf', '.png', '.jpg', '.jpeg', '.gif', '.mp4', '.avi',
            '.doc', '.docx', '.xls', '.xlsx', '.csv', '.json', '.xml', '.zip'
        )
        if any(text.lower().endswith(ext) for ext in common_extensions):
            return False
        
        # Base64 should only contain: A-Za-z0-9+/=
        base64_chars = set(string.ascii_letters + string.digits + "+/=")
        
        # Check first 100 chars for base64 validity (skip line breaks)
        sample = text[:100].replace('\n', '').replace('\r', '')
        if not all(c in base64_chars for c in sample):
            return False
        
        return True

    def _handle_file_input(self, file_input: str, file_extension: str = "bin") -> tuple[str, bool]:
        """Handle both file paths and base64-encoded file content.
        
        Args:
            file_input: Either a file path or base64-encoded file content
            file_extension: Extension to use for temporary files (without dot)
            
        Returns:
            Tuple of (file_path, is_temp_file) where is_temp_file indicates if cleanup is needed
        """
        # Check if input is base64 encoded (remote client upload)
        try:
            if file_input.startswith("data:") and ";" in file_input and "," in file_input:
                # Data URI format: data:image/png;base64,{content}
                # Extract MIME type and determine file extension
                mime_part, content = file_input.split(",", 1)
                mime_type = mime_part.split(":")[1].split(";")[0]
                
                # Determine extension from MIME type
                extension = mimetypes.guess_extension(mime_type)
                if extension:
                    file_extension = extension.lstrip(".")
                
                # Decode base64 content
                try:
                    # Fix padding if needed (base64 strings must be multiple of 4)
                    missing_padding = len(content) % 4
                    if missing_padding:
                        content += '=' * (4 - missing_padding)
                    decoded = base64.b64decode(content)
                except Exception as decode_error:
                    logger.warning(f"Failed to decode data URI base64 content: {decode_error}")
                    return file_input, False

            elif self._is_likely_base64(file_input):
                # Likely base64 content (remote upload)
                try:
                    decoded = base64.b64decode(file_input, validate=True)
                except Exception:
                    # Not base64, treat as file path
                    return file_input, False
            else:
                # Treat as file path
                return file_input, False

            # Write decoded content to temporary file
            temp_file = tempfile.NamedTemporaryFile(
                suffix=f".{file_extension}",
                delete=False
            )
            temp_file.write(decoded)
            temp_file.close()
            
            logger.debug(f"Created temporary file from base64 content: {temp_file.name}")
            return temp_file.name, True
            
        except base64.binascii.Error as e:
            # Expected: invalid base64 content
            logger.debug(f"Not base64 encoded, treating as file path: {type(e).__name__}")
            return file_input, False
        except Exception as e:
            # Unexpected errors
            logger.warning(f"Error processing file input: {e}. Treating as file path.")
            return file_input, False


    def _sanitize_content_block(self, content_block: Dict[str, Any], max_length: int = 8000) -> Dict[str, Any]:
        """Sanitize content_block to ensure it's safe for JSON serialization and AI API consumption."""
        if not isinstance(content_block, dict):
            logger.warning(f"content_block is not a dict, converting: {type(content_block)}")
            content_block = {"type": "text", "text": str(content_block)}
        
        if "type" not in content_block:
            content_block["type"] = "text"
        
        content_type = content_block.get("type", "text")
        
        if content_type == "text" and "text" in content_block:
            text = content_block["text"]
            if not isinstance(text, str):
                text = str(text)
            
            # Fix escaped quotes (\' → ')
            text = text.replace("\\'", "'")
            
            # Remove control characters except tab/newline/carriage return
            text = ''.join(
                char if (ord(char) >= 32 or ord(char) in (9, 10, 13)) else ' '
                for char in text
            )
            
            # Normalize whitespace (3+ newlines -> 2 newlines)
            text = re.sub(r'\n{3,}', '\n\n', text)
            
            # Truncate if too long
            if len(text) > max_length:
                truncate_at = text.rfind('.', max_length - 500, max_length)
                if truncate_at == -1:
                    truncate_at = text.rfind('\n', max_length - 500, max_length)
                if truncate_at == -1:
                    truncate_at = max_length
                text = text[:truncate_at] + "\n\n... [content truncated due to length]"
            
            content_block["text"] = text
        
        return content_block

    @staticmethod
    def _vlm_content(resp_text: str) -> str:
        """Safely extract the message content from a VLM chat-completion response.

        vLLM/OpenAI error bodies (e.g. 400 BadRequest, 401 Unauthorized) do NOT
        contain a 'choices' key, so a raw ['choices'][0][...]['content'] read turns
        a real error into a confusing KeyError. Return the content when present,
        else raise ValueError with the actual error body so callers can report it.
        """
        if isinstance(resp_text, dict):
            data = resp_text
        else:
            try:
                data = json.loads(resp_text)
            except (json.JSONDecodeError, TypeError) as e:
                raise ValueError(f"VLM response is not valid JSON: {str(resp_text)[:500]!r} ({e})")

        # Error-shaped responses: {"error": {...}} / {"detail": ...} / {"error": "..."}
        if isinstance(data, dict) and (data.get("error") or data.get("detail")):
            err = data.get("error") or data.get("detail")
            if isinstance(err, dict):
                err = err.get("message") or str(err)
            raise ValueError(f"VLM API returned an error: {err}")

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise ValueError(f"VLM response missing 'choices[0].message.content': {str(data)[:500]!r} ({e})")
        if not isinstance(content, str):
            content = str(content)
        return content

    @property
    def timeout(self) -> float:
        """Get timeout value, using config if not set explicitly."""
        return self._timeout if self._timeout is not None else config.timeout

    async def __aenter__(self) -> "CompoidClient":
        """Async context manager entry."""
        headers = {
            "User-Agent": config.get_user_agent(),
            # Authenticated read-back: restricted records (home communities
            # user-<id>) 403 on anonymous reads; the repo key works as Bearer
            # on GET /api/records (verified 2026-09-16).
            "Authorization": f"Bearer {config.repo_api_key}",
        }
        self._client = httpx.AsyncClient(timeout=self.timeout, headers=headers)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    def _build_url(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Build the full URL with query parameters."""
        url = f"{config.repo_api_base_url}/{endpoint.lstrip('/')}"

        if params is None:
            params = {}

        # Add sort for polite pool access
        if self.sort:
            params["sort"] = self.sort

        if params:
            url += f"?{urlencode(params, doseq=True)}"

        return url

    async def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make an async HTTP request to the Compoid API."""
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        async with self._rate_limiter:
            url = self._build_url(endpoint, params)

            if config.log_api_requests:
                logger.debug(f"Making request to: {url}")

            try:
                response = await self._client.get(url)
                response.raise_for_status()

                if config.log_api_requests:
                    logger.debug(f"Response status: {response.status_code}")

                return response.json()
            except httpx.HTTPStatusError as e:
                error_msg = f"Compoid API error ({e.response.status_code}): {e.response.text}{_hint_for(e.response.status_code)}"
                logger.error(error_msg)
                raise Exception(error_msg)
            except httpx.RequestError as e:
                error_msg = f"Request failed: {str(e)}"
                logger.error(error_msg)
                raise Exception(error_msg)

    async def get_works(
        self,
        work_id: Optional[str] = None,
        community_id: Optional[str] = None,
        search: Optional[str] = None,
        sort: Optional[str] = None,
        filter_title: Optional[str] = None,
        filter_description: Optional[str] = None,
        filter_community: Optional[str] = None,
        filter_keywords: Optional[Dict[str, str]] = None,
        filter_creators: Optional[Dict[str, str]] = None,
        filter_exact_date: Optional[str] = None,
        filter_access_status: Optional[str] = None,
        filter_resource_type: Optional[str] = None,
        filter_file_type: Optional[str] = None,
        page: int = 1,
        size: int = 5,
        select: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get works from Compoid.
        
        Args:
            work_id: Specific record ID to retrieve
            community_id: Search for records in specific communiy ID
            search: Search query
            sort: Sort order
            filter_title: Search in title
            filter_description: Search in description
            filter_community: Search by community
            filter_keywords: keywords
            filter_creators: Filter by authors and models
            filter_exact_date: Filter by exact date
            filter_access_status: Filter by access status
            filter_resource_type: Filter by resource type
            filter_file_type: Filter by file type
            page: Page number
            size: Results per page
            select: Fields to select
        """
        if work_id:
            endpoint = f"records/{work_id}"
            params: Dict[str, Any] = {}

        elif community_id:
            endpoint = f"communities/{community_id}/records"
            params: Dict[str, Any] = {
                "page": page,
                "size": min(size, 30)
            }
            # Build filters
            filters = []

            if filter_title:
                for key, value in filter_title.items():
                    filters.append(f"({key}:{value})")
            if filter_description:
                for key, value in filter_description.items():
                    filters.append(f"({key}:{value})")
            if filter_exact_date:
                for key, value in filter_exact_date.items():
                    filters.append(f"({key}:{value})")
            if filter_access_status:
                for key, value in filter_access_status.items():
                    filters.append(f"({key}:{value})")
            if filter_resource_type:
                for key, value in filter_resource_type.items():
                    filters.append(f"({key}:{value})")
            if filter_file_type:
                for key, value in filter_file_type.items():
                    filters.append(f"({key}:{value})")
            if filter_keywords:
                for key, value in filter_keywords.items():
                    filters.append(f"({key}:{value})")
            if filter_creators:
                for key, value in filter_creators.items():
                    filters.append(f"({key}:{value})")
            if filter_community:
                community = None # search by path
            if search:
                filters.insert(0, f"({search})")  # Add search term first
            if filters:
                params["q"] = "AND".join(filters)
            if sort:
                params["sort"] = sort
            if select:
                params["select"] = ",".join(select)

        else:
            endpoint = "records"
            params: Dict[str, Any] = {
                "page": page,
                "size": min(size, 30)
            }

            # Build filters
            filters = []

            if filter_title:
                for key, value in filter_title.items():
                    filters.append(f"({key}:{value})")
            if filter_description:
                for key, value in filter_description.items():
                    filters.append(f"({key}:{value})")
            if filter_community:
                for key, value in filter_community.items():
                    filters.append(f"({key}:{value})")
            if filter_exact_date:
                for key, value in filter_exact_date.items():
                    filters.append(f"({key}:{value})")
            if filter_access_status:
                for key, value in filter_access_status.items():
                    filters.append(f"({key}:{value})")
            if filter_resource_type:
                for key, value in filter_resource_type.items():
                    filters.append(f"({key}:{value})")
            if filter_file_type:
                for key, value in filter_file_type.items():
                    filters.append(f"({key}:{value})")
            if filter_keywords:
                for key, value in filter_keywords.items():
                    filters.append(f"({key}:{value})")
            if filter_creators:
                for key, value in filter_creators.items():
                    filters.append(f"({key}:{value})")
            if search:
                filters.insert(0, f"({search})")  # Add search term first
            if filters:
                params["q"] = "AND".join(filters)
            if sort:
                params["sort"] = sort
            if select:
                params["select"] = ",".join(select)

        return await self._make_request(endpoint, params)

    async def get_communities(
        self,
        community_id: Optional[str] = None,
        search: Optional[str] = None,
        filter_title: Optional[str] = None,
        filter_description: Optional[str] = None,
        filter_access_status: Optional[str] = None,
        sort: Optional[str] = None,
        page: int = 1,
        size: int = 20,
        select: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get communities from Compoid."""
        if community_id:
            endpoint = f"communities/{community_id}"
            params: Dict[str, Any] = {}
        elif search == 'all communities':
            endpoint = f"communities"
            params: Dict[str, Any] = {
                "page": page,
                "size": min(size, 30)
            }
        elif search == 'compoid communities':
            endpoint = f"communities"
            params: Dict[str, Any] = {
                "page": page,
                "size": min(size, 30)
            }
        elif search == 'communities':
            endpoint = f"communities"
            params: Dict[str, Any] = {
                "page": page,
                "size": min(size, 30)
            }
        else:
            endpoint = "communities"
            params: Dict[str, Any] = {
                "page": page,
                "size": min(size, 30)
            }

            # Build filters
            filters = []

            if filter_title:
                for key, value in filter_title.items():
                    filters.append(f"({key}:{value})")
            if filter_description:
                for key, value in filter_description.items():
                    filters.append(f"({key}:{value})")
            if filter_access_status:
                for key, value in filter_access_status.items():
                    filters.append(f"({key}:{value})")
            if search:
                    filters.insert(0, f"({search})")  # Add search term first
            if filters:
                params["q"] = "AND".join(filters)
            if sort:
                params["sort"] = sort
            if select:
                params["select"] = ",".join(select)

        return await self._make_request(endpoint, params)

    @staticmethod
    def _collection_node(entry: Any) -> Optional[Dict[str, Any]]:
        """Extract the collection node from a collection-trees entry.

        The API returns each collection as a wrapper dict like
        {"root": <id>, "<id>": {<node fields>}}. Plain node dicts are
        tolerated as well so the helper stays forward-compatible.
        """
        if not isinstance(entry, dict):
            return None
        root = entry.get("root")
        if isinstance(root, int):
            node = entry.get(str(root))
            if isinstance(node, dict) and "id" in node:
                return node
        for key, value in entry.items():
            if key != "root" and isinstance(value, dict) and "id" in value:
                return value
        if "id" in entry and "children" in entry:
            return entry
        return None

    def _flatten_collection_trees(self, trees_response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Flatten a collection-trees response into a flat list of collections.

        The endpoint returns {tree_id: {title, slug, collections: [...]}} and
        each collection node may nest further collections under "children".
        Each returned dict carries id, title, slug, tree, order, depth,
        num_records, search_query and records_url.
        """
        collections: List[Dict[str, Any]] = []

        def _walk(entries: Any, tree_name: str) -> None:
            for entry in entries or []:
                node = self._collection_node(entry)
                if not node:
                    continue
                links = node.get("links") if isinstance(node.get("links"), dict) else {}
                collections.append({
                    "id": node.get("id"),
                    "title": node.get("title"),
                    "slug": node.get("slug"),
                    "tree": tree_name,
                    "order": node.get("order"),
                    "depth": node.get("depth"),
                    "num_records": node.get("num_records"),
                    "search_query": node.get("search_query"),
                    "records_url": links.get("search"),
                })
                _walk(node.get("children"), tree_name)

        for tree in (trees_response or {}).values():
            if isinstance(tree, dict):
                _walk(tree.get("collections"), tree.get("title"))

        return collections

    async def _resolve_community_id(self, community: str) -> str:
        """Resolve a community ID or slug to its UUID.

        The collection-trees endpoint only works with UUIDs, so slugs are
        resolved through the public community endpoint first.
        """
        response = await self.get_communities(community_id=community)
        community_id = response.get("id") if isinstance(response, dict) else None
        if not community_id:
            raise Exception(f"Could not resolve community: {community}")
        return community_id

    async def get_collection_trees(self, community: str) -> List[Dict[str, Any]]:
        """Get a community's collections from its collection trees.

        Args:
            community: Community ID (UUID) or slug.

        Returns:
            Flat list of collections (see _flatten_collection_trees).
        """
        community_id = await self._resolve_community_id(community)
        response = await self._make_request(f"communities/{community_id}/collection-trees")
        return self._flatten_collection_trees(response)

    async def get_collection_records(
        self,
        collection_id: int,
        q: Optional[str] = None,
        size: int = 10
    ) -> Dict[str, Any]:
        """Get the records of a collection.

        The API automatically applies the collection's own search_query; a
        provided ``q`` is AND-ed on top of it. The endpoint rejects a
        ``sort`` parameter, so records come back in Compoid's default order.

        Args:
            collection_id: Numeric collection ID (from get_collection_trees).
            q: Optional additional search query.
            size: Page size (max 50).

        Returns:
            Standard search response with a "hits" object.
        """
        params: Dict[str, Any] = {"size": min(int(size), 50)}
        if q:
            params["q"] = q
        return await self._make_request(f"collections/{collection_id}/records", params)

    async def download_pdf(self, archive_url: str, file_path: str) -> bool:
        """Download a PDF from a given URL.
        
        Args:
            archive_url: URL of the PDF to download
            file_path: Local path where to save the PDF
            
        Returns:
            True if download was successful, False otherwise
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        try:
            async with self._rate_limiter:
                if config.log_api_requests:
                    logger.debug(f"Downloading ZIP archive from: {archive_url}")

                response = await self._client.get(archive_url, follow_redirects=True)
                response.raise_for_status()

                # Check if response contains PDF content
                content_type = response.headers.get("content-type", "").lower()
                if "zip" not in content_type:
                    logger.warning(f"Downloaded content may not be ZIP archive: {content_type}")

                with open(file_path, "wb") as f:
                    f.write(response.content)

                if config.log_api_requests:
                    logger.debug(f"ZIP archive saved to: {file_path}")

                return True

        except httpx.HTTPStatusError as e:
            error_msg = f"file archive download failed ({e.response.status_code}): {e.response.text}"
            logger.error(error_msg)
            return False
        except httpx.RequestError as e:
            error_msg = f"file archive download request failed: {str(e)}"
            logger.error(error_msg)
            return False
        except OSError as e:
            error_msg = f"Failed to save archive file: {str(e)}"
            logger.error(error_msg)
            return False

    async def upload_record(
        self,
        community_id: str,
        file_upload: str,
        creators: list[str],
        filter_title: Optional[str] = None,
        filter_description: Optional[str] = None,
        filter_references: list[str] = None,
        filter_subjects: list[str] = None,
        filter_keywords: list[str] = None,
        filter_resource_type: list[str] = None
    ) -> Dict[str, Any]:
        """Create or update Compoid record.
        
        Args:
            community_id: Community ID where to upload the record
            file_upload: Local file path OR base64-encoded file content from remote client
            creators: List of creators
            filter_title: Record title
            filter_description: Record description
            filter_references: List of references
            filter_subjects: List of subject display names (https://www.compoid.com/subjects)
            filter_keywords: List of keywords
            filter_resource_type: List of resource types
        Returns:
            Tuple of (success, record_id) where success is bool and record_id is str
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        # Handle both local file paths and base64 content from remote clients
        file_path, is_temp_file = self._handle_file_input(file_upload)
        
        try:
            mime_type, _ = mimetypes.guess_type(file_path)

            # some extensions (like .md) aren't registered by default
            if not mime_type and file_path.lower().endswith(".md"):
                mime_type = "text/markdown"

            # Fallback if detection fails
            if mime_type is None:
                mime_type = "application/octet-stream"


            # 2. Determine the content block type for the payload
            content_block = {}
            if mime_type.startswith("image/"):
                content_block = {
                    "type": "image_url",
                    "image_url": {"url": f"file://{file_path}"}
                }
            elif mime_type.startswith("video/"):
                content_block = {
                    "type": "video_url",
                    "video_url": {"url": f"file://{file_path}"}
                }
            elif mime_type.startswith("application/msword") or mime_type.startswith("application/vnd.openxmlformats-officedocument.wordprocessingml.document"):
                try:
                    result = subprocess.run(
                        ['antiword', file_path],
                        capture_output=True,
                        text=True,
                        timeout=30  # Prevent hanging on large files
                    )
                    if result.returncode == 0:
                        text_content = result.stdout
                    else:
                        logger.warning(f"antiword extraction failed with code {result.returncode}: {result.stderr}")
                        text_content = f"[Word document: {os.path.basename(file_path)}]"
                except FileNotFoundError:
                    logger.warning("antiword not installed - using filename as fallback for Word document extraction")
                    text_content = f"[Word document: {os.path.basename(file_path)}]"
                except subprocess.TimeoutExpired:
                    logger.warning("antiword extraction timed out after 30 seconds")
                    text_content = f"[Word document: {os.path.basename(file_path)}]"
                except Exception as e:
                    logger.warning(f"Unexpected error during antiword extraction: {e}")
                    text_content = f"[Word document: {os.path.basename(file_path)}]"
                
                content_block = {
                    "type": "text", 
                    "text": text_content
                }
            elif mime_type.startswith("text/"):
                def load_text_file(path):
                    with open(path, "r", encoding="utf-8") as f:
                        return f.read()
                md_content = load_text_file(file_path)
                content_block = {
                    "type": "text", 
                    "text": md_content
                }
                # Sanitize the content block for AI API
                content_block = self._sanitize_content_block(content_block)
            elif mime_type == "application/pdf":
                # PDF files - extract the text and send it as a text block.
                # (Previously sent as an image_url/file:// block, which the VLM
                # cannot parse as an image and fails on.)
                pdf_text = ""
                try:
                    import pdftotext  # pip package (poppler-backed), see pyproject.toml
                    with open(file_path, "rb") as _f:
                        _pdf = pdftotext.PDF(_f)
                        _pages = []
                        for _i, _page in enumerate(_pdf):
                            if _i >= 20:  # keep first 20 pages to bound prompt size
                                break
                            _t = str(_page).strip()
                            if _t:
                                _pages.append(_t)
                        pdf_text = "\n\n".join(_pages)
                except Exception as e:
                    logger.warning(f"pdftotext extraction failed: {e}")
                    pdf_text = ""
                if not pdf_text.strip():
                    pdf_text = f"[PDF document: {os.path.basename(file_path)}]"
                content_block = {
                    "type": "text",
                    "text": pdf_text
                }
                content_block = self._sanitize_content_block(content_block)
            elif mime_type in ("application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"):
                # Excel files - include filename reference
                content_block = {
                    "type": "text", 
                    "text": f"[Spreadsheet: {os.path.basename(file_path)}]"
                }
            elif mime_type == "application/zip":
                # ZIP archives - include filename reference
                content_block = {
                    "type": "text", 
                    "text": f"[Archive: {os.path.basename(file_path)}]"
                }
            else:
                content_block = {
                    "type": "text", 
                    "text": "the file extension is not supported, describe the file based on its name and mime type: " + mime_type
                }

            try:
                file_loader = FileSystemLoader(_TEMPLATES_DIR)
                env = Environment(loader=file_loader)
                env.filters['jsonify'] = json.dumps
                dictf = env.get_template('communitydict-extended.json')
                rendered_json_str_f = dictf.render()
                communitydict = json.loads(rendered_json_str_f)
                community = community_id.lower() if isinstance(community_id, str) else community_id
                community_keywords = communitydict.get(community, "") or "AI-bots-playground"
                systemroleschema = env.get_template('system-role-schema.json').render(communityid=community_keywords)
                community_restricted = False
                if len(community) != 36:
                    dicts = env.get_template('communitydict.json')
                    rendered_json_str_s = dicts.render()
                    communitydict = json.loads(rendered_json_str_s)
                    community = communitydict.get(community, "") or None
                    if community is None:
                        # Home communities (user-<id>) are created by the bootstrap sweep and
                        # are not in the static dict; resolve via the API. Restricted
                        # communities require restricted records, otherwise publish fails
                        # with: "A public record cannot be included in a restricted community."
                        resolved, community_restricted = resolve_community_visibility(community_id)
                        if resolved is None:
                            error_msg = (
                                f"Community '{community_id}' not found. Use a valid community slug "
                                f"(e.g. 'physics' - browse https://www.compoid.com/communities), a "
                                f"community UUID, or a home community slug 'user-<id>'."
                            )
                            logger.error(error_msg)
                            raise ValueError(error_msg)
                        community = resolved
                else:
                    # UUID input: pick up visibility so restricted home communities get
                    # restricted records. Public communities fail open (unchanged behavior).
                    _, community_restricted = resolve_community_visibility(community)
                dictr = env.get_template('resourcetypedict.json')
                rendered_json_str_r = dictr.render()
                resourcetypedict = json.loads(rendered_json_str_r)
                
                # Determine resource_type based on MIME type if not provided
                if filter_resource_type is None:
                    if mime_type.startswith("image/"):
                        resource_type = "image"
                    elif mime_type.startswith("video/"):
                        resource_type = "video"
                    elif mime_type.startswith("text/"):
                        resource_type = "publication"  # Text files are publications
                    elif mime_type == "application/pdf":
                        resource_type = "publication"
                    elif mime_type.startswith("application/vnd.ms-excel") or mime_type.startswith("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"):
                        resource_type = "dataset"
                    elif mime_type.startswith("application/msword") or mime_type.startswith("application/vnd.openxmlformats-officedocument.wordprocessingml.document"):
                        resource_type = "publication"
                    elif mime_type.startswith("audio/"):
                        resource_type = "audio"
                    else:
                        resource_type = "other"
                else:
                    resource_type = filter_resource_type
                
                # Get display name from resource type ID
                resourcetype = resourcetypedict.get(resource_type, "Other")

                async with self._rate_limiter:
                    if config.log_api_requests:
                        logger.debug(f"Creating record with files: {file_path}")

                    headers = {"Content-Type": "application/json", 'Authorization': f"Bearer {config.ai_api_key}"}
                    ratingspayload = {
                        "model": config.ai_model,
                        "messages": [
                            {"role": "system", "content": (
                                f"You are a content access rater. Rate the provided content and return ONLY a JSON object with exactly "
                                f"two keys: \"contentCategory\" (the string {community_keywords}) and \"contentAccessRatings\" - an array of five "
                                f"objects, one per item name General, Sensitive, Proprietary, Open Access, Private, each "
                                f"{{\"itemName\": <item name>, \"value\": <integer 0-9>}} where 9 = fully open/public and 0 = maximally "
                                f"sensitive/restricted. Return the rating object only - do not repeat the schema, do not wrap the result "
                                f"in a tool call, do not use markdown. Reference schema for the value bounds: {systemroleschema}"
                            )},
                            {"role": "user", "content": [
                              content_block,
                              {
                                "type": "text",
                                "text": "Rate the content access of the provided content. Return the JSON object described above only - no explanation, no schema, no tool call."
                              },
                            ]
                          }
                        ],
                        "temperature": 0.1,
                        "frequency_penalty": 0.2,
                        "presence_penalty": 0.2,
                        "max_tokens": 1200,
                        "stream": False,
                        "chat_template_kwargs": {
                            "enable_thinking": False
                        },
                        "response_format": { 'type': 'json_object' },
                        "top_p": 0.95
                    }

                    start=time.time()
                    ratingsresponse = requests.request("POST", f"{config.ai_api_base_url}/chat/completions", json=ratingspayload, headers=headers)
                    print(time.time()-start)

                    read_ratingsfile = json.loads(ratingsresponse.text)
                    if ratingsresponse.status_code != 200 or read_ratingsfile.get("error") or read_ratingsfile.get("detail"):
                        err_body = (read_ratingsfile.get("error") or read_ratingsfile.get("detail") or ratingsresponse.text)
                        raise ValueError(f"VLM content-rating call failed (HTTP {ratingsresponse.status_code}): {str(err_body)[:500]}")

                    # Fetch live subject vocabulary so the VLM can classify content topics
                    subject_vocab = []
                    subject_anchors = {}
                    try:
                        vocab_resp = requests.get(
                            f"{config.repo_api_base_url}/subjects?size=200",
                            headers={"Authorization": f"Bearer {config.repo_api_key}"},
                            timeout=15
                        )
                        for h in vocab_resp.json()['hits']['hits']:
                            if h.get('subject'):
                                subject_vocab.append(h['subject'])
                                subject_anchors[h['subject']] = h['id'].split('#', 1)[1] if '#' in h.get('id', '') else h['subject'].replace(" ", "_")
                        logger.debug(f"Loaded {len(subject_vocab)} subjects for VLM classification")
                    except Exception as e:
                        logger.warning(f"Subject vocabulary fetch failed, VLM subjects will be empty: {e}")

                    payload = {
                        "model": config.ai_model,
                        "messages": [
                            {"role": "user", "content": [
                              content_block,
                              {
                                "type": "text",
                                "text": f"Analyze this file and provide a SINGLE JSON object with ALL of these fields:\n\n1. 'caption_llama32_short': A short one-sentence description of the file\n2. 'caption_qwen25vl_long': A detailed description with grounding and specific details\n3. 'wd_tagger_eva02_l': An array of 10-20 relevant tags (objects, style, file type, topics, etc.)\n4. 'subjects': An array of UP TO 4 subject names chosen EXACTLY (verbatim, do not modify casing or wording) from this fixed list: {json.dumps(subject_vocab)}. Do NOT include 'Artificial Intelligence' - it is added automatically.\n\nIMPORTANT: Return ALL FOUR FIELDS in ONE JSON object. Do not stop after the first field. The 'subjects' array MUST contain only names that appear verbatim in the list above. If the file content does not match any subject in the list, return an empty array []."
                              }
                            ]
                          }
                        ],
                        "temperature": 0.3,
                        "chat_template_kwargs": {"enable_thinking": False},
                        "frequency_penalty": 0.2,
                        "presence_penalty": 0.2,
                        "max_tokens": 1200,
                        "stream": False,
                        "top_p": 0.95,
                    }

                    start=time.time()
                    response = requests.request("POST", f"{config.ai_api_base_url}/chat/completions", json=payload, headers=headers)
 
       
                    if file_path.startswith("/projects/"):
                        clean_file_upload = file_path.split("/")[-1]  # Extract just the filename
                    elif file_path.startswith("/tmp/"):
                        clean_file_upload = file_path.split("/")[-1]  # Extract just the filename
                    else:
                        clean_file_name = re.sub(r'[<>:"/\\|?*]', '', file_path)
                        clean_file_upload = clean_file_name.replace(' ', '_')[:50]

                read_file = json.loads(response.text)
                if response.status_code != 200 or read_file.get("error") or read_file.get("detail"):
                    err_body = (read_file.get("error") or read_file.get("detail") or response.text)
                    raise ValueError(f"VLM caption call failed (HTTP {response.status_code}): {str(err_body)[:500]}")

                file_name = clean_file_upload
                default_preview = clean_file_upload
                youtube_video_id = ''
                today = date.today()
                update_date = today.strftime("%Y-%m-%d")
                publication_date = (today - timedelta(days = 1)).strftime("%Y-%m-%d")
                mod_string_cogvlm_short1 = read_file.get('model', '')
                caption_cogvlm_short = re.sub('\"', '*', str(mod_string_cogvlm_short1))
                default_reference = f"https://www.compoid.com/communities/{community}/browse"
                references = filter_references
                mod_string_cogvlm_long1 = read_file.get('object', '')
                mod_string_cogvlm_long2 =  re.sub('\n\t', '<p></p>', str(mod_string_cogvlm_long1))
                mod_string_cogvlm_long3 =  re.sub('\n\n', '<p></p>', str(mod_string_cogvlm_long2))
                caption_cogvlm_long = re.sub('\"', '*', str(mod_string_cogvlm_long3))
                # caption_llama32_medium = read_file.get('id', '')

                # Parse JSON response directly instead of using string manipulation
                try:
                    content_raw = self._vlm_content(read_file)
                    
                    # The AI may return multiple JSON objects, parse them all
                    merged_json = {}
                    
                    # Find all JSON-like content (between { and })
                    json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
                    json_matches = re.findall(json_pattern, content_raw, re.DOTALL)
                    
                    for json_text in json_matches:
                        try:
                            parsed = json.loads(json_text.strip())
                            # Merge into combined dict
                            merged_json.update(parsed)
                        except json.JSONDecodeError:
                            # Skip invalid JSON fragments
                            continue
                    
                    # Extract fields from merged JSON with fallbacks
                    ai_short_caption = merged_json.get('caption_llama32_short', '')
                    ai_long_caption = merged_json.get('caption_qwen25vl_long', '')
                    ai_tags = merged_json.get('wd_tagger_eva02_l', [])
                    ai_subjects_raw = merged_json.get('subjects', [])

                    # Validate VLM-returned subjects against the live vocabulary (case-insensitive exact match)
                    vocab_lookup = {s.lower().strip(): s for s in subject_vocab}
                    valid_ai_subjects = []
                    for subj in (ai_subjects_raw if isinstance(ai_subjects_raw, list) else []):
                        if isinstance(subj, str):
                            norm = subj.lower().strip()
                            if norm in vocab_lookup:
                                canonical = vocab_lookup[norm]
                                if canonical != DEFAULT_SUBJECT and canonical not in valid_ai_subjects:
                                    valid_ai_subjects.append(canonical)
                    # Cap at 4: the template always appends the default subject,
                    # and the record schema allows a maximum of 5 total.
                    valid_ai_subjects = valid_ai_subjects[:4]

                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    logger.warning(f"Failed to parse AI response JSON: {e}")
                    ai_short_caption = ''
                    ai_long_caption = ''
                    ai_tags = []
                    valid_ai_subjects = []

                # Determine final values based on provided filters
                if filter_title:
                    caption_llama32_short = filter_title
                else:
                    caption_llama32_short = ai_short_caption
                
                if filter_description:
                    caption_qwen25vl_long = filter_description
                else:
                    caption_qwen25vl_long = ai_long_caption

                # Process keywords
                # Check if filter_keywords is None or empty list
                if not filter_keywords:
                    # Use AI-extracted tags
                    limit = 20
                    keywords_dict = {}

                    # Convert list to dict with None values
                    if isinstance(ai_tags, list):
                        for tag in ai_tags[:limit]:
                            # Clean up the tag (remove asterisks, trim whitespace)
                            clean_tag = tag.strip().strip('*').strip()
                            if clean_tag:
                                keywords_dict[clean_tag] = None

                else:
                    limit = 20
                    keywords_dict = {}
                    count = 0
                    # Convert list to dict format for template
                    if isinstance(filter_keywords, list):
                        for keyword in filter_keywords[:limit]:
                            keywords_dict[keyword] = None
                    elif isinstance(filter_keywords, dict):
                        for key, value in filter_keywords.items():
                            if count < limit:
                                keywords_dict[key] = value
                                count += 1
                            else:
                                break

                # Safe helper function to extract ratings with fallback defaults
                def get_rating(ratings_list, item_name, default=1.0):
                    """Safely get a rating value with a default fallback (0-1 scale)."""
                    try:
                        return next(item['value'] for item in ratings_list if item['itemName'] == item_name)
                    except (StopIteration, KeyError, TypeError):
                        return default

                content_string = self._vlm_content(read_ratingsfile)
                content_data = json.loads(content_string)
                # The VLM can answer in three shapes: a bare ratings array,
                # a plain object with 'contentAccessRatings', or a tool-call
                # shape with an 'arguments' envelope - unwrap whichever it
                # uses.
                if isinstance(content_data, list):
                    content_ratings = content_data
                else:
                    if isinstance(content_data, dict):
                        _args = content_data.get('arguments')
                        if isinstance(_args, str):
                            try:
                                _args = json.loads(_args)
                            except (json.JSONDecodeError, ValueError):
                                _args = None
                        if isinstance(_args, dict):
                            content_data = _args
                    _ratings = (
                        content_data.get('contentAccessRatings')
                        if isinstance(content_data, dict)
                        else None
                    )
                    # Safely extract contentAccessRatings (0-1 scale)
                    content_ratings = (
                        _ratings if isinstance(_ratings, list) else []
                    )
                general_weights = get_rating(content_ratings, 'General', 9)
                sensitive_weights = get_rating(content_ratings, 'Sensitive', 0)
                proprietary_weights = get_rating(content_ratings, 'Proprietary', 0)
                open_access_weights = get_rating(content_ratings, 'Open Access', 0)
                private_weights = get_rating(content_ratings, 'Private', 0)


                # Determine content class safely
                if content_ratings:
                    highest_item = max(content_ratings, key=lambda x: x.get('value', 0))
                    content_class = highest_item.get('itemName', 'General')
                else:
                    # No ratings in the VLM response (e.g. it echoed the
                    # schema instead of rating the content). Fail closed
                    # instead of defaulting to General/public: classify as
                    # 'Unknown' so classify_content maps it to a restricted
                    # record rather than publishing un-evaluated content.
                    logger.warning(
                        f"VLM ratings response has no contentAccessRatings "
                        f"(unusable response), failing closed to restricted: "
                        f"{str(content_data)[:300]}"
                    )
                    content_class = 'Unknown'
                content_class_id, content_class_title = classify_content(content_class)

                limit = 5
                creators_dict = {}
                count = 0
                # Convert list to dict format for template
                if isinstance(creators, list):
                    for creator in creators[:limit]:
                        creators_dict[creator] = None
                elif isinstance(creators, dict):
                    for key, value in creators.items():
                        if count < limit:
                            creators_dict[key] = value
                            count += 1
                        else:
                            break

                limit = 5
                references_dict = {}
                count = 0
                # Convert list to dict format for template
                if isinstance(filter_references, list):
                    for reference in filter_references[:limit]:
                        references_dict[reference] = None
                elif isinstance(filter_references, dict):
                    for key, value in filter_references.items():
                        if count < limit:
                            references_dict[key] = value
                            count += 1
                        else:
                            break

                limit = 5
                subjects_dict = {}
                count = 0
                # Determine effective subjects: explicit filter_subjects wins; else VLM-derived
                effective_subjects = filter_subjects if filter_subjects else (valid_ai_subjects or None)
                if effective_subjects and isinstance(effective_subjects, list) and not filter_subjects:
                    logger.info(f"Using {len(valid_ai_subjects)} VLM-classified subjects: {valid_ai_subjects}")
                # Convert list to dict format for template
                if isinstance(effective_subjects, list):
                    for subject in effective_subjects[:limit]:
                        if subject and subject != DEFAULT_SUBJECT:
                            subjects_dict[subject] = None
                elif isinstance(effective_subjects, dict):
                    for key, value in effective_subjects.items():
                        if count < limit:
                            subjects_dict[key] = value
                            count += 1
                        else:
                            break
                # Anchor map: subject name -> URL anchor fragment. Prefer the live
                # API anchor (handles punctuated subjects like "Agriculture, forestry,
                # and fisheries" -> Agriculture_forestry_and_fisheries), else naive
                # spaces->underscores.
                subject_map = {subject: (subjects_dict[subject] or subject_anchors.get(subject) or subject.replace(" ", "_")) for subject in subjects_dict}
                
                API_ENDPOINT = f"{config.repo_api_base_url}/records"
                headers = {"Content-Type": "application/json", 'Authorization': f"Bearer {config.repo_api_key}"}
                uploadfileheaders = {"Content-Type": "application/octet-stream", 'Authorization': f"Bearer {config.repo_api_key}"}
                payload = {'q': '(metadata.title:"%s")'% (caption_llama32_short)}
                upddraftreq = requests.get(API_ENDPOINT, params=payload)

                upddraftresponse = upddraftreq.json()
                total_records = upddraftresponse['hits']['total']

                uploadtemplate = env.get_template('compoid-template.json')
                filestemplate = env.get_template('compoid-filestemplate.json')
                metadatafiles = filestemplate.render(file_name=file_name)
              
                if total_records != 0:
                    versions_url = upddraftresponse['hits']['hits'][0]['links']['versions']
                    versionsreq = requests.post(versions_url, headers=headers)                   
                    draftresponse = versionsreq.json()
                    if 'links' not in draftresponse:
                        raise ValueError(f"Invenio version creation failed (HTTP {versionsreq.status_code}): {str(draftresponse)[:1000]}")

                    data = uploadtemplate.render(file_name=file_name, short_caption=caption_llama32_short, long_caption=caption_qwen25vl_long, short_alt_caption=caption_cogvlm_short, long_alt_caption=caption_cogvlm_long, default_preview=default_preview, youtube_video_id=youtube_video_id, references=references_dict,
                            content_class=content_class, content_class_id=content_class_id, content_class_title=content_class_title, general_weights=general_weights, sensitive_weights=sensitive_weights, keywords=keywords_dict, community_restricted=community_restricted, content_public=content_class_id == 'public', community_keywords=community_keywords, publication_date=publication_date, update_date=update_date, creators=creators_dict,
                            proprietary_weights=proprietary_weights, open_access_weights=open_access_weights, private_weights=private_weights, default_reference=default_reference, subjects=subjects_dict, subject_map=subject_map, default_subject=DEFAULT_SUBJECT, default_subject_map=DEFAULT_SUBJECT_MAP, resource_type=resource_type, resourcetype=resourcetype)
                    draft_url = draftresponse['links']['self']
                    publish_url = draftresponse['links']['publish']
                    files_url = draftresponse['links']['files']
                    filesreq = requests.post(files_url, data=metadatafiles, headers=headers)
                    draftreq = requests.put(draft_url, data=data, headers=headers)
                    filesresponse = filesreq.json()

                    # filesresponse is a dict with 'entries' list
                    first_file = filesresponse['entries'][0]
                    pngcontent_url = first_file['links']['content']
                    pngcommit_url = first_file['links']['commit']
                    with open(file_path, 'rb') as png:
                        datafilespng = png.read()
                    pngcontentreq = requests.put(
                        pngcontent_url, data=datafilespng, headers=uploadfileheaders)
                    if pngcontentreq.status_code == 200:
                        print("Base64 encoded file uploaded successfully!")
                    else:
                        print(f"Error uploading file: {pngcontentreq.status_code}")
                        print(pngcontentreq.text)
                    pngcommitreq = requests.post(pngcommit_url, headers=headers)
                    publishreq = requests.post(publish_url, headers=headers)
                    if publish_url.startswith("https://www.compoid.com/api/records"):
                        record_id_1 = publish_url.replace('/draft/actions/publish', '')
                        record_id = record_id_1.split("/")[-1]  # Extract just the ID

                else:
                    reviewtemplate = env.get_template('compoid-reviewtemplate.json')
                    metadatareview = reviewtemplate.render(community=community)
                    data = uploadtemplate.render(file_name=file_name, short_caption=caption_llama32_short, long_caption=caption_qwen25vl_long, short_alt_caption=caption_cogvlm_short, long_alt_caption=caption_cogvlm_long, default_preview=default_preview, youtube_video_id=youtube_video_id, references=references_dict,
                            content_class=content_class, content_class_id=content_class_id, content_class_title=content_class_title, general_weights=general_weights, sensitive_weights=sensitive_weights, keywords=keywords_dict, community_restricted=community_restricted, content_public=content_class_id == 'public', community_keywords=community_keywords, publication_date=publication_date, update_date=update_date, creators=creators_dict,
                            proprietary_weights=proprietary_weights, open_access_weights=open_access_weights, private_weights=private_weights, default_reference=default_reference, subjects=subjects_dict, subject_map=subject_map, default_subject=DEFAULT_SUBJECT, default_subject_map=DEFAULT_SUBJECT_MAP, resource_type=resource_type, resourcetype=resourcetype)
                    draftreq = requests.post(API_ENDPOINT, data=data, headers=headers)
                    draftresponse = draftreq.json()

                    if 'links' not in draftresponse:
                        body = str(draftresponse)[:1000]
                        extra = ""
                        if "Not a valid value" in body:
                            extra = (
                                "\nHint: a field failed enum validation. 'resource_type' must be one of: "
                                "analysis, image, video, audio, publication, document, software, project, dataset, "
                                "presentation, workflow, tutorial, other; 'subjects' must be display names from "
                                "https://www.compoid.com/subjects (max 5)."
                            )
                        raise ValueError(f"Invenio rejected draft creation (HTTP {draftreq.status_code}): {body}{extra}")

                    draft_url = draftresponse['links']['self']
                    review_url = draftresponse['links']['review']
                    files_url = draftresponse['links']['files']
                    filesreq = requests.post(files_url, data=metadatafiles, headers=headers)
                    filesresponse = filesreq.json()

                    first_file = filesresponse['entries'][0]
                    pngcontent_url = first_file['links']['content']
                    pngcommit_url = first_file['links']['commit']
                    with open(file_path, 'rb') as png:
                        datafilespng = png.read()
                    pngcontentreq = requests.put(
                        pngcontent_url, data=datafilespng, headers=uploadfileheaders)
                    if pngcontentreq.status_code == 200:
                        print("Base64 encoded file uploaded successfully!")
                    else:
                        print(f"Error uploading file: {pngcontentreq.status_code}")
                        print(pngcontentreq.text)
                    pngcommitreq = requests.post(pngcommit_url, headers=headers)
                    draftreq = requests.put(draft_url, data=data, headers=headers)
                    reviewreq = requests.put(review_url, data=metadatareview, headers=headers)
                    reviewresponse = reviewreq.json()
                    submit_url = reviewresponse['links']['actions']['submit']
                    submitreq = requests.post(submit_url, headers=headers)
                    submitresponse = submitreq.json()

                    # Check if /api/communities/{community}/members returns 403 (forbidden)
                    members_endpoint = f"{config.repo_api_base_url}/communities/{community}/members"
                    members_check = requests.get(members_endpoint, headers=headers)
                    if members_check.status_code == 403:
                        logger.warning(f"Not a member of {members_endpoint}. Approval request for draft {draft_url} created.")
                        record_id = draftresponse.get('id', None)
                        return True, record_id, draft_url
                    else:
                        publish_url = submitresponse['links']['actions']['accept']
                        publishreq = requests.post(publish_url, headers=headers)
                        record_id = submitresponse['topic']['record']


                if config.log_api_requests and publish_url:
                    logger.debug(f"Record published: {publish_url}")
                elif config.log_api_requests and not publish_url:
                    logger.debug(f"Draft request pending review: {draft_url}")

                return True, record_id

            except httpx.HTTPStatusError as e:
                error_msg = f"Failed to create a record ({e.response.status_code}): {e.response.text}{_hint_for(e.response.status_code)}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            except httpx.RequestError as e:
                error_msg = f"Network error while creating a record: {str(e)} (check network/API reachability and retry)"
                logger.error(error_msg)
                raise ValueError(error_msg)
            except OSError as e:
                error_msg = (f"File error while creating a record: {str(e)} "
                             f"(check the file exists on the MCP server host, or use a data URI / /projects/ path)")
                logger.error(error_msg)
                raise ValueError(error_msg)
        
        finally:
            # Clean up temporary files created from base64 content
            if is_temp_file:
                try:
                    os.unlink(file_path)
                    logger.debug(f"Cleaned up temporary file: {os.path.basename(file_path)}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary file {file_path}: {e}")

    async def modify_record(
        self,
        work_id: str,
        file_upload: Optional[str] = None,
        filter_creators: Optional[list[str]] = None,
        filter_title: Optional[str] = None,
        filter_description: Optional[str] = None,
        filter_references: Optional[list[str]] = None,
        filter_subjects: Optional[list[str]] = None,
        filter_keywords: Optional[list[str]] = None,
        filter_resource_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update an existing Compoid record using InvenioRDM versioning API.
        
        This method creates a new draft version from the existing record and:
        - Links files from the previous version (avoiding re-upload/duplication)
        - Only updates metadata fields that are explicitly provided
        - Allows optional file replacement if file_upload is provided
        
        Args:
            work_id: ID of the record to modify (required)
            community_id: ID of the community to associate with the record (optional)
            file_upload: Local file path OR base64-encoded file content (optional - keeps existing files if not provided)
            filter_creators: List of creators (optional)
            filter_title: Record title (optional)
            filter_description: Record description (optional)
            filter_references: List of references (optional)
            filter_subjects: List of subject display names (optional - keeps existing subjects if not provided, https://www.compoid.com/subjects)
            filter_keywords: List of keywords (optional)
            filter_resource_type: Resource type ID (optional)
        Returns:
            Tuple of (success, record_id) where success is bool and record_id is str
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        try:
            # Step 1: Get existing record details
            logger.debug(f"Fetching existing record: {work_id}")
            existing_record = await self.get_works(work_id=work_id)

            if not existing_record:
                error_msg = (
                    f"Record '{work_id}' not found. Use a published record PID "
                    f"(e.g. '4171t-rc787'); drafts are not addressable until published."
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

            # Step 2: Create new draft version from existing record
            # POST /api/records/{id}/versions
            communities_endpoint = f"records/{work_id}/communities"
            versions_endpoint = f"records/{work_id}/versions"
            versions_url = f"{config.repo_api_base_url}/{versions_endpoint}"
            communities_url = f"{config.repo_api_base_url}/{communities_endpoint}"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config.repo_api_key}"
            }

            async with self._rate_limiter:
                response = await self._client.get(communities_url, headers=headers)
                response.raise_for_status()
                communities_response = response.json()
                if communities_response.get('hits', {}).get('hits'):
                    community_id = communities_response['hits']['hits'][0]['id']
            if not community_id:
                error_msg = (
                    f"Could not determine the community for record {work_id} (no community "
                    f"association found on the record). Pass community_id to set one explicitly."
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

            logger.debug(f"Creating new draft version from record: {work_id}")
            async with self._rate_limiter:
                response = await self._client.post(versions_url, headers=headers)
                response.raise_for_status()
                draft_response = response.json()
            
            draft_id = draft_response.get("id")
            draft_url = draft_response["links"]["self"]
            files_url = draft_response["links"]["files"]
            
            logger.debug(f"Created draft version: {draft_id}")

            # Check if source record is metadata-only and mark draft accordingly
            async with self._rate_limiter:
                record_check = await self._client.get(f"https://www.compoid.com/api/records/{work_id}", headers=headers)
                record_data = record_check.json()

            # After creating the draft (after logger.debug(f"Created draft version: {draft_id}"))
            logger.debug(f"Created draft version: {draft_id}")

            # Check if source record is metadata-only
            record_url = f"https://www.compoid.com/api/records/{work_id}"
            async with self._rate_limiter:
                record_check = await self._client.get(record_url, headers=headers)
                record_data = record_check.json()

            is_metadata_only = record_data.get("access", {}).get("status") == "metadata-only"

            # Step 3: Link files from previous version (unless new file_upload provided)
            if not file_upload:
                if is_metadata_only:
                    logger.debug(f"Record {work_id} is metadata-only, skipping file import")
                else:
                    import_files_url = f"{draft_url}/actions/files-import"
                    logger.debug(f"Linking files from previous version")
                    async with self._rate_limiter:
                        import_response = await self._client.post(import_files_url, headers=headers)
                        import_response.raise_for_status()
                    logger.debug(f"Successfully linked files from previous version")

            # Step 4: Prepare metadata updates
            # Use provided values or fall back to existing record values
            existing_metadata = existing_record.get("metadata", {})
            
            final_title = filter_title if filter_title is not None else existing_metadata.get("title")
            final_description = filter_description if filter_description is not None else existing_metadata.get("description")
            
            # Extract creators from existing metadata (person_or_org structure)
            if filter_creators is not None:
                final_creators = filter_creators
            else:
                # Extract just the names from existing creators structure
                existing_creators_list = existing_metadata.get("creators", [])
                final_creators = [creator.get("person_or_org", {}).get("name", "") for creator in existing_creators_list if creator.get("person_or_org", {}).get("name")]
            
            # Extract keywords from existing contributors with role "keyword"
            if filter_keywords is not None:
                final_keywords = filter_keywords
            else:
                existing_contributors = existing_metadata.get("contributors", [])
                final_keywords = [
                    contrib.get("person_or_org", {}).get("name", "") 
                    for contrib in existing_contributors 
                    if contrib.get("role", {}).get("id") == "keyword" and contrib.get("person_or_org", {}).get("name")
                ]
            
            # Extract references from existing metadata
            if filter_references is not None:
                final_references = filter_references
            else:
                existing_refs = existing_metadata.get("references", [])
                final_references = [ref.get("reference", "") for ref in existing_refs if ref.get("reference")]

            # Extract subjects from existing metadata
            if filter_subjects is not None:
                final_subjects = filter_subjects
            else:
                existing_subjects = existing_metadata.get("subjects", [])
                final_subjects = [subj.get("subject", "") for subj in existing_subjects if subj.get("subject")]
            
            final_resource_type = filter_resource_type if filter_resource_type is not None else existing_metadata.get("resource_type", {}).get("id", "other")
            
            # Extract content ratings from additional_titles if they exist
            existing_additional_titles = existing_metadata.get("additional_titles", [])

            content_ratings = {}
            for title_entry in existing_additional_titles:
                rating_type = title_entry.get("type", {}).get("id")
                rating_value = title_entry.get("title", "0.5")
                if rating_type:
                    content_ratings[rating_type] = rating_value
            
            # Step 5: If file_upload is provided, upload new file
            if file_upload:
                # Handle both local file paths and base64 content
                file_path, is_temp_file = self._handle_file_input(file_upload)
                
                try:
                    # Get filename
                    if file_path.startswith("/projects/"):
                        clean_file_upload = file_path.split("/")[-1]
                    elif file_path.startswith("/tmp/"):
                        clean_file_upload = file_path.split("/")[-1]
                    else:
                        clean_file_name = re.sub(r'[<>:"/\\|?*]', '', file_path)
                        clean_file_upload = clean_file_name.replace(' ', '_')[:50]
                    
                    # Create file metadata
                    filestemplate_loader = FileSystemLoader(_TEMPLATES_DIR)
                    filestemplate_env = Environment(loader=filestemplate_loader)
                    filestemplate = filestemplate_env.get_template('compoid-filestemplate.json')
                    metadatafiles = filestemplate.render(file_name=clean_file_upload)
                    
                    # POST file metadata
                    async with self._rate_limiter:
                        files_create_response = await self._client.post(
                            files_url,
                            data=metadatafiles,
                            headers=headers
                        )
                        files_create_response.raise_for_status()
                        files_response = files_create_response.json()
                    
                    # Upload file content
                    first_file = files_response['entries'][0]
                    pngcontent_url = first_file['links']['content']
                    pngcommit_url = first_file['links']['commit']
                    
                    uploadfileheaders = {
                        "Content-Type": "application/octet-stream",
                        "Authorization": f"Bearer {config.repo_api_key}"
                    }
                    
                    with open(file_path, 'rb') as file_data:
                        datafiles = file_data.read()
                    
                    async with self._rate_limiter:
                        upload_response = await self._client.put(
                            pngcontent_url,
                            data=datafiles,
                            headers=uploadfileheaders
                        )
                        upload_response.raise_for_status()
                    
                    # Commit file
                    async with self._rate_limiter:
                        commit_response = await self._client.post(pngcommit_url, headers=headers)
                        commit_response.raise_for_status()
                    
                    logger.debug(f"Successfully uploaded new file: {clean_file_upload}")
                finally:
                    # Clean up temp file if needed
                    if is_temp_file:
                        try:
                            os.unlink(file_path)
                            logger.debug(f"Cleaned up temporary file: {os.path.basename(file_path)}")
                        except Exception as e:
                            logger.warning(f"Failed to clean up temporary file {file_path}: {e}")
            
            # Step 6: Update metadata using template
            file_loader = FileSystemLoader(_TEMPLATES_DIR)
            env = Environment(loader=file_loader)
            env.filters['jsonify'] = json.dumps
            
            # Load resource type dict
            dictr = env.get_template('resourcetypedict.json')
            rendered_json_str_r = dictr.render()
            resourcetypedict = json.loads(rendered_json_str_r)
            resourcetype = resourcetypedict.get(final_resource_type, "Other")

            # Load community dict
            dictf = env.get_template('communitydict-extended.json')
            rendered_json_str_f = dictf.render()
            communitydict = json.loads(rendered_json_str_f)
            community = community_id.lower() if isinstance(community_id, str) else community_id
            community_keywords = communitydict.get(community, "") or "AI-bots-playground"
            if len(community) != 36:
                dicts = env.get_template('communitydict.json')
                rendered_json_str_s = dicts.render()
                communitydict = json.loads(rendered_json_str_s)
                community = communitydict.get(community, "") or None
                if community is None:
                    error_msg = (
                        f"Community '{community_id}' not found. Use a valid community slug, "
                        f"a community UUID, or a home community slug 'user-<id>'."
                    )
                    logger.error(error_msg)
                    raise ValueError(error_msg)
            # The community here is a UUID (resolved from the record's parent), so the
            # user-<id> slug prefix can't be tested; check visibility via the API.
            # Home communities are restricted and require restricted records, otherwise
            # the version publish fails: "A public record cannot be included in a
            # restricted community." Fail open to public on lookup errors.
            _, community_restricted = resolve_community_visibility(community)
            # Convert lists to dicts for template
            creators_dict = {}
            if isinstance(final_creators, list):
                for creator in final_creators[:5]:
                    creators_dict[creator] = None
            elif isinstance(final_creators, dict):
                creators_dict = dict(list(final_creators.items())[:5])
            
            references_dict = {}
            if isinstance(final_references, list):
                for reference in final_references[:5]:
                    references_dict[reference] = None
            elif isinstance(final_references, dict):
                references_dict = dict(list(final_references.items())[:5])

            # Convert subjects to dicts for template (dedupe the default, which
            # the template always appends)
            subjects_dict = {}
            if isinstance(final_subjects, list):
                for subject in final_subjects[:5]:
                    if subject and subject != DEFAULT_SUBJECT:
                        subjects_dict[subject] = None
            elif isinstance(final_subjects, dict):
                for subject in list(final_subjects.keys())[:5]:
                    if subject and subject != DEFAULT_SUBJECT:
                        subjects_dict[subject] = final_subjects[subject]
            # Anchor map: subject name -> URL anchor fragment (spaces -> underscores)
            subject_map = {subject: (subjects_dict[subject] or subject.replace(" ", "_")) for subject in subjects_dict}
            
            keywords_dict = {}
            if isinstance(final_keywords, list):
                for keyword in final_keywords[:20]:
                    keywords_dict[keyword] = None
            elif isinstance(final_keywords, dict):
                keywords_dict = dict(list(final_keywords.items())[:20])
            
            # Prepare dates
            today = date.today()
            update_date = today.strftime("%Y-%m-%d")

            publication_date = existing_metadata.get("publication_date", (today - timedelta(days=1)).strftime("%Y-%m-%d"))
            # Use existing or default values for fields not being updated
            file_name = clean_file_upload if file_upload else existing_metadata.get("title", "metadata-update")
            default_preview = file_name
            youtube_video_id = ''
            default_reference = f"https://www.compoid.com/records/{work_id}"
            
            # Content ratings - use extracted values from existing metadata or defaults
            def get_rating_weight(rating_type, default=0.5):
                """Convert rating from string (e.g., '0.80000') to integer weight (8)."""
                rating_str = content_ratings.get(rating_type, str(default))
                try:
                    return int(float(rating_str) * 10)
                except (ValueError, TypeError):
                    return int(default * 10)

            general_weights = get_rating_weight('general', 0.5)
            sensitive_weights = get_rating_weight('sensitive', 0.0)
            proprietary_weights = get_rating_weight('proprietary', 0.0)
            open_access_weights = get_rating_weight('open_access', 0.0)
            private_weights = get_rating_weight('private', 0.0)
            
            # Determine content class from highest rating
            if content_ratings:
                max_rating_type = max(
                    ['general', 'sensitive', 'proprietary', 'open_access', 'private'],
                    key=lambda x: float(content_ratings.get(x, '0'))
                )
                content_class = max_rating_type.capitalize()
            else:
                # No ratings stored on the existing record - fail closed
                # instead of defaulting to General/public (Unknown maps to
                # restricted via classify_content).
                content_class = 'Unknown'
            content_class_id, content_class_title = classify_content(content_class)
            
            caption_llama32_short = final_title or "Updated Record"
            caption_qwen25vl_long = final_description or "Metadata update"
            caption_cogvlm_short = f"Record {work_id}"
            caption_cogvlm_long = final_description or "Metadata update"
            
            # Render updated metadata
            uploadtemplate = env.get_template('compoid-template.json')
            data = uploadtemplate.render(
                file_name=file_name,
                short_caption=caption_llama32_short,
                long_caption=caption_qwen25vl_long,
                short_alt_caption=caption_cogvlm_short,
                long_alt_caption=caption_cogvlm_long,
                default_preview=default_preview,
                youtube_video_id=youtube_video_id,
                references=references_dict,
                content_class=content_class,
                content_class_id=content_class_id,
                content_class_title=content_class_title,
                general_weights=general_weights,
                sensitive_weights=sensitive_weights,
                proprietary_weights=proprietary_weights,
                open_access_weights=open_access_weights,
                private_weights=private_weights,
                keywords=keywords_dict,
                community_restricted=community_restricted,
                content_public=content_class_id == 'public',
                community_keywords=community_keywords,
                publication_date=publication_date,
                update_date=update_date,
                creators=creators_dict,
                default_reference=default_reference,
                subjects=subjects_dict,
                subject_map=subject_map,
                default_subject=DEFAULT_SUBJECT,
                default_subject_map=DEFAULT_SUBJECT_MAP,
                resource_type=final_resource_type,
                resourcetype=resourcetype
            )
            
            # Step 7: Update draft metadata
            # Parse the rendered template as JSON
            metadata_dict = json.loads(data)

            # For metadata-only records, ADD files.enabled: false to the payload
            if is_metadata_only:
                metadata_dict["files"] = {"enabled": False}
                logger.debug(f"Added files.enabled=false to metadata-only record")
                data = json.dumps(metadata_dict)
            async with self._rate_limiter:
                update_response = await self._client.put(
                    draft_url,
                    data=data,
                    headers=headers
                )
                update_response.raise_for_status()
            
            logger.debug(f"Successfully updated draft metadata")
            
            # Step 8: Publish the draft
            # Construct publish URL from draft URL
            publish_url = f"{draft_url}/actions/publish"
            async with self._rate_limiter:
                publish_response = await self._client.post(publish_url, headers=headers)
                publish_response.raise_for_status()
                published_record = publish_response.json()
            
            record_id = published_record.get("id", work_id)
            
            logger.debug(f"Successfully published updated record: {record_id}")
            
            if config.log_api_requests:
                logger.debug(f"Record updated and published: {record_id}")
            
            return True, record_id
        
        except httpx.HTTPStatusError as e:
            error_msg = f"Failed to modify record {work_id} ({e.response.status_code}): {e.response.text}{_hint_for(e.response.status_code)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        except httpx.RequestError as e:
            error_msg = f"Network error while modifying record {work_id}: {str(e)} (check network/API reachability and retry)"
            logger.error(error_msg)
            raise ValueError(error_msg)
        except OSError as e:
            error_msg = f"File error while modifying record {work_id}: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error modifying record {work_id}: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

    async def create_community(
        self,
        slug: str,
        title: str,
        description: Optional[str] = None,
        community_type: Optional[str] = None,
        curation_policy: Optional[str] = None,
        website: Optional[str] = None,
        visibility: str = "public",
        member_policy: str = "open",
        record_policy: str = "open",
    ) -> Dict[str, Any]:
        """Create a new community via POST /api/communities.

        Args:
            slug: URL-compatible identifier (max 100 chars), e.g. "my-community"
            title: Human-readable title (required, max 250 chars)
            description: Short description (optional, max 2000 chars)
            community_type: Type id, e.g. "repository", "workspace", "finanalysis"
            curation_policy: Curation policy text (optional, html allowed)
            website: External website URL (optional)
            visibility: "public" or "restricted" (default "public")
            member_policy: "open" or "closed" (default "open")
            record_policy: "open" or "closed" (default "open")

        Returns:
            Community dict on success, or raises on error.
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        url = f"{config.repo_api_base_url}/communities"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.repo_api_key}",
        }

        payload: Dict[str, Any] = {
            "slug": slug,
            "access": {
                "visibility": visibility,
                "member_policy": member_policy,
                "record_policy": record_policy,
            },
            "metadata": {
                "title": title,
            },
        }

        if description:
            payload["metadata"]["description"] = description
        if community_type:
            payload["metadata"]["type"] = {"id": community_type}
        if curation_policy:
            payload["metadata"]["curation_policy"] = curation_policy
        if website:
            payload["metadata"]["website"] = website

        import json as _json
        async with self._rate_limiter:
            response = await self._client.post(url, content=_json.dumps(payload), headers=headers)
            response.raise_for_status()
            return response.json()

    async def update_community(
        self,
        community_id: str,
        slug: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        community_type: Optional[str] = None,
        curation_policy: Optional[str] = None,
        website: Optional[str] = None,
        visibility: Optional[str] = None,
        member_policy: Optional[str] = None,
        record_policy: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update an existing community via PUT /api/communities/{id}.

        The InvenioRDM PUT endpoint requires a full replacement body, so we
        first GET the current community and merge the caller-supplied fields.

        Args:
            community_id: UUID or slug of the community to update
            slug: New URL slug (optional)
            title: New title (optional)
            description: New description (optional)
            community_type: New type id (optional)
            curation_policy: New curation policy (optional)
            website: New website URL (optional)
            visibility: New visibility ("public"/"restricted") (optional)
            member_policy: New member policy ("open"/"closed") (optional)
            record_policy: New record policy ("open"/"closed") (optional)

        Returns:
            Updated community dict on success, or raises on error.
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.repo_api_key}",
        }

        # Step 1: fetch the current community so we can do a full PUT
        get_url = f"{config.repo_api_base_url}/communities/{community_id}"
        async with self._rate_limiter:
            get_resp = await self._client.get(get_url, headers=headers)
            get_resp.raise_for_status()
            current = get_resp.json()

        # Step 2: merge updates
        if slug:
            current["slug"] = slug
        if visibility:
            current.setdefault("access", {})["visibility"] = visibility
        if member_policy:
            current.setdefault("access", {})["member_policy"] = member_policy
        if record_policy:
            current.setdefault("access", {})["record_policy"] = record_policy
        if title:
            current.setdefault("metadata", {})["title"] = title
        if description is not None:
            current.setdefault("metadata", {})["description"] = description
        if community_type:
            current.setdefault("metadata", {})["type"] = {"id": community_type}
        if curation_policy is not None:
            current.setdefault("metadata", {})["curation_policy"] = curation_policy
        if website is not None:
            current.setdefault("metadata", {})["website"] = website

        # Step 3: PUT the merged payload
        # Strip read-only fields that the API rejects on write
        for key in ("id", "created", "updated", "revision_id", "links", "files",
                    "versions", "parent", "stats", "status", "is_published",
                    "custom_fields", "tombstone", "deletion_status"):
            current.pop(key, None)

        put_url = f"{config.repo_api_base_url}/communities/{community_id}"
        import json as _json
        async with self._rate_limiter:
            put_resp = await self._client.put(put_url, content=_json.dumps(current), headers=headers)
            put_resp.raise_for_status()
            return put_resp.json()

    async def delete_record(self, work_id: str) -> Dict[str, Any]:
        """Delete a published record via DELETE /api/records/{work_id}.

        The InvenioRDM API returns 204 No Content on success (the record is
        tombstoned and drops out of search). Only published records are
        addressable - drafts have no PID until published.

        Args:
            work_id: published record PID (e.g. '4171t-rc787')

        Returns:
            {"deleted": True, "work_id": work_id} on success.
            Raises Exception with an actionable hint on 403/404/other errors.
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        url = f"{config.repo_api_base_url}/records/{work_id}"
        headers = {
            "Authorization": f"Bearer {config.repo_api_key}",
        }

        async with self._rate_limiter:
            response = await self._client.delete(url, headers=headers)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                error_msg = f"Compoid API error ({e.response.status_code}): {e.response.text}{_hint_for(e.response.status_code)}"
                logger.error(error_msg)
                raise Exception(error_msg)

            if response.status_code == 204:
                return {"deleted": True, "work_id": work_id}
            try:
                return {"deleted": True, "work_id": work_id, **response.json()}
            except Exception:
                return {"deleted": True, "work_id": work_id}
