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

from compoid_mcp.config import config
from compoid_mcp.logutil import logger
## create record
import requests
import json
import re
import time
from datetime import date, timedelta
from jinja2 import Environment, FileSystemLoader

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

    @property
    def timeout(self) -> float:
        """Get timeout value, using config if not set explicitly."""
        return self._timeout if self._timeout is not None else config.timeout

    async def __aenter__(self) -> "CompoidClient":
        """Async context manager entry."""
        headers = {"User-Agent": config.get_user_agent()}
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
                error_msg = f"Compoid API error ({e.response.status_code}): {e.response.text}"
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
            elif mime_type == "application/pdf":
                # PDF files - include filename reference since we can't extract text directly
                content_block = {
                    "type": "image_url",
                    "image_url": {"url": f"file://{file_path}"}
                }
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
                file_loader = FileSystemLoader('src/compoid_mcp/templates')
                env = Environment(loader=file_loader)
                env.filters['jsonify'] = json.dumps
                dictf = env.get_template('communitydict-extended.json')
                rendered_json_str_f = dictf.render()
                communitydict = json.loads(rendered_json_str_f)
                community = community_id.lower() if isinstance(community_id, str) else community_id
                community_keywords = communitydict.get(community, "") or "AI-bots-playground"
                systemroleschema = env.get_template('system-role-schema.json').render(communityid=community_keywords)
                if len(community) != 36:
                    dicts = env.get_template('communitydict.json')
                    rendered_json_str_s = dicts.render()
                    communitydict = json.loads(rendered_json_str_s)
                    community = communitydict.get(community, "") or None
                    if community is None:
                        error_msg = f"Community {community_id} not found: {str(e)}"
                        logger.error(error_msg)
                        return False, None
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
                    imgpayload = {
                        "model": config.ai_model,
                        "messages": [
                            {"role": "system", "content": f"Evaluate the image content raitings using 'get_content_raitings' JSON schema: {systemroleschema}"},
                            {"role": "user", "content": [
                              content_block,
                              {
                                "type": "text",
                                "text": "Output content raitings for the image as JSON, use the 'get_content_raitings' tools and schema"
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
                            "enable_thinking": True
                        },
                        "response_format": { 'type': 'json_object' },
                        "top_p": 0.95
                    }


                    start=time.time()
                    imgresponse = requests.request("POST", f"{config.ai_api_base_url}/chat/completions", json=imgpayload, headers=headers)
                    print(time.time()-start)

                    read_imgfile = json.loads(imgresponse.text)
                    payload = {
                        "model": config.ai_model,
                        "messages": [
                            {"role": "user", "content": [
                              content_block,
                              {
                                "type": "text",
                                "text": "Analyze this file and provide a SINGLE JSON object with ALL of these fields:\n\n1. 'caption_llama32_short': A short one-sentence description of the file\n2. 'caption_qwen25vl_long': A detailed description with grounding and specific details\n3. 'wd_tagger_eva02_l': An array of 10-20 relevant tags (objects, style, file type, topics, etc.)\n\nIMPORTANT: Return ALL THREE FIELDS in ONE JSON object. Do not stop after the first field."
                              }
                            ]
                          }
                        ],
                        "temperature": 0.3,
                        "extra_body": {
                            "chat_template_kwargs": {
                                "enable_thinking": False
                            }
                        },
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

                file_name = clean_file_upload
                default_preview = clean_file_upload
                youtube_video_id = ''
                today = date.today()
                update_date = today.strftime("%Y-%m-%d")
                publication_date = (today - timedelta(days = 1)).strftime("%Y-%m-%d")
                mod_string_cogvlm_short1 = read_file['model']
                caption_cogvlm_short = re.sub('\"', '*', str(mod_string_cogvlm_short1))
                default_reference = "https://huggingface.co/" + caption_cogvlm_short
                references = filter_references
                mod_string_cogvlm_long1 = read_file['object']
                mod_string_cogvlm_long2 =  re.sub('\n\t', '<p></p>', str(mod_string_cogvlm_long1))
                mod_string_cogvlm_long3 =  re.sub('\n\n', '<p></p>', str(mod_string_cogvlm_long2))
                caption_cogvlm_long = re.sub('\"', '*', str(mod_string_cogvlm_long3))
                caption_llama32_medium = read_file['id']

                # Parse JSON response directly instead of using string manipulation
                try:
                    content_raw = read_file['choices'][0]['message']['content']
                    
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

                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    logger.warning(f"Failed to parse AI response JSON: {e}")
                    ai_short_caption = ''
                    ai_long_caption = ''
                    ai_tags = []

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
                def get_rating(ratings_list, item_name, default=5):
                    """Safely get a rating value with a default fallback."""
                    try:
                        return next(item['value'] for item in ratings_list if item['itemName'] == item_name)
                    except (StopIteration, KeyError, TypeError):
                        return default

                content_string = read_imgfile['choices'][0]['message']['content']
                content_data = json.loads(content_string)

                # Safely extract contentRatings with defaults
                content_ratings = content_data.get('contentRatings', [])
                general_weights = get_rating(content_ratings, 'General', 8)
                sensitive_weights = get_rating(content_ratings, 'Sensitive', 2)
                questionable_weights = get_rating(content_ratings, 'Questionable', 1)
                explicit_weights = get_rating(content_ratings, 'Explicit', 1)
                educational_weights = get_rating(content_ratings, 'Educational', 5)
                inspirational_weights = get_rating(content_ratings, 'Inspirational', 5)
                informational_weights = get_rating(content_ratings, 'Informational', 5)
                violence_weights = get_rating(content_ratings, 'Violence', 1)
                entertaining_weights = get_rating(content_ratings, 'Entertaining', 5)
                promotional_weights = get_rating(content_ratings, 'Promotional', 1)
                
                # Determine content class safely
                if content_ratings:
                    highest_item = max(content_ratings, key=lambda x: x.get('value', 0))
                    content_class = highest_item.get('itemName', 'General')
                else:
                    content_class = 'General'

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

                    data = uploadtemplate.render(file_name=file_name, short_caption=caption_llama32_short, medium_caption=caption_llama32_medium, long_caption=caption_qwen25vl_long, short_alt_caption=caption_cogvlm_short, long_alt_caption=caption_cogvlm_long, default_preview=default_preview, youtube_video_id=youtube_video_id, references=references_dict,
                            content_class=content_class, general_weights=general_weights, sensitive_weights=sensitive_weights, questionable_weights=questionable_weights, explicit_weights=explicit_weights, keywords=keywords_dict, community_keywords=community_keywords, publication_date=publication_date, update_date=update_date, creators=creators_dict,
                            educational_weights=educational_weights, inspirational_weights=inspirational_weights, informational_weights=informational_weights, violence_weights=violence_weights, entertaining_weights=entertaining_weights, promotional_weights=promotional_weights, default_reference=default_reference, resource_type=resource_type, resourcetype=resourcetype)
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
                    data = uploadtemplate.render(file_name=file_name, short_caption=caption_llama32_short, medium_caption=caption_llama32_medium, long_caption=caption_qwen25vl_long, short_alt_caption=caption_cogvlm_short, long_alt_caption=caption_cogvlm_long, default_preview=default_preview, youtube_video_id=youtube_video_id, references=references_dict,
                            content_class=content_class, general_weights=general_weights, sensitive_weights=sensitive_weights, questionable_weights=questionable_weights, explicit_weights=explicit_weights, keywords=keywords_dict, community_keywords=community_keywords, publication_date=publication_date, update_date=update_date, creators=creators_dict,
                            educational_weights=educational_weights, inspirational_weights=inspirational_weights, informational_weights=informational_weights, violence_weights=violence_weights, entertaining_weights=entertaining_weights, promotional_weights=promotional_weights, default_reference=default_reference, resource_type=resource_type, resourcetype=resourcetype)
                    draftreq = requests.post(API_ENDPOINT, data=data, headers=headers)
                    draftresponse = draftreq.json()

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
                error_msg = f"HTTPStatusError Failed to create a record ({e.response.status_code}): {e.response.text}"
                logger.error(error_msg)
                return False, None
            except httpx.RequestError as e:
                error_msg = f"RequestError Failed to create a record: {str(e)}"
                logger.error(error_msg)
                return False, None
            except OSError as e:
                error_msg = f"Failed to create a record: {str(e)}"
                logger.error(error_msg)
                return False, None
        
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
                return False, None
                      
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
                logger.error(f"Could not determine community_id for record {work_id}")
                return False, None

            logger.debug(f"Creating new draft version from record: {work_id}")
            async with self._rate_limiter:
                response = await self._client.post(versions_url, headers=headers)
                response.raise_for_status()
                draft_response = response.json()
            
            draft_id = draft_response.get("id")
            draft_url = draft_response["links"]["self"]
            files_url = draft_response["links"]["files"]
            
            logger.debug(f"Created draft version: {draft_id}")
            
            # Step 3: Link files from previous version (unless new file_upload provided)
            # POST /api/records/{id}/draft/actions/files-import
            if not file_upload:
                # Construct the files-import URL from the draft URL
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
                    filestemplate_loader = FileSystemLoader('src/compoid_mcp/templates')
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
            file_loader = FileSystemLoader('src/compoid_mcp/templates')
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
                    error_msg = f"Community {community_id} not found: {str(e)}"
                    logger.error(error_msg)
                    return False, None
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
            
            general_weights = get_rating_weight('general', 0.8)
            sensitive_weights = get_rating_weight('sensitive', 0.2)
            questionable_weights = get_rating_weight('questionable', 0.1)
            explicit_weights = get_rating_weight('explicit', 0.1)
            educational_weights = get_rating_weight('educational', 0.5)
            inspirational_weights = get_rating_weight('inspirational', 0.5)
            informational_weights = get_rating_weight('informational', 0.5)
            violence_weights = get_rating_weight('violence', 0.1)
            entertaining_weights = get_rating_weight('entertaining', 0.5)
            promotional_weights = get_rating_weight('promotional', 0.1)
            
            # Determine content class from highest rating
            if content_ratings:
                max_rating_type = max(
                    ['general', 'sensitive', 'questionable', 'explicit', 'educational', 'inspirational', 'informational', 'violence', 'entertaining', 'promotional'],
                    key=lambda x: float(content_ratings.get(x, '0'))
                )
                content_class = max_rating_type.capitalize()
            else:
                content_class = 'General'
            
            caption_llama32_short = final_title or "Updated Record"
            caption_llama32_medium = work_id
            caption_qwen25vl_long = final_description or "Metadata update"
            caption_cogvlm_short = f"Record {work_id}"
            caption_cogvlm_long = final_description or "Metadata update"
            
            # Render updated metadata
            uploadtemplate = env.get_template('compoid-template.json')
            data = uploadtemplate.render(
                file_name=file_name,
                short_caption=caption_llama32_short,
                medium_caption=caption_llama32_medium,
                long_caption=caption_qwen25vl_long,
                short_alt_caption=caption_cogvlm_short,
                long_alt_caption=caption_cogvlm_long,
                default_preview=default_preview,
                youtube_video_id=youtube_video_id,
                references=references_dict,
                content_class=content_class,
                general_weights=general_weights,
                sensitive_weights=sensitive_weights,
                questionable_weights=questionable_weights,
                explicit_weights=explicit_weights,
                keywords=keywords_dict,
                community_keywords=community_keywords,
                publication_date=publication_date,
                update_date=update_date,
                creators=creators_dict,
                educational_weights=educational_weights,
                inspirational_weights=inspirational_weights,
                informational_weights=informational_weights,
                violence_weights=violence_weights,
                entertaining_weights=entertaining_weights,
                promotional_weights=promotional_weights,
                default_reference=default_reference,
                resource_type=final_resource_type,
                resourcetype=resourcetype
            )
            
            # Step 7: Update draft metadata
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
            error_msg = f"HTTPStatusError Failed to modify record ({e.response.status_code}): {e.response.text}"
            logger.error(error_msg)
            return False, None
        except httpx.RequestError as e:
            error_msg = f"RequestError Failed to modify record: {str(e)}"
            logger.error(error_msg)
            return False, None
        except OSError as e:
            error_msg = f"Failed to modify record: {str(e)}"
            logger.error(error_msg)
            return False, None
        except Exception as e:
            error_msg = f"Unexpected error modifying record: {str(e)}"
            logger.error(error_msg)
            return False, None

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
