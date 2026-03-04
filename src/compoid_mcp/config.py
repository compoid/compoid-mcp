"""Configuration management for Compoid MCP Server."""

import os
from typing import Optional


class CompoidConfig:
    """Configuration for Compoid MCP Server."""

    def __init__(self):
        """Initialize configuration from environment variables."""
        self.sort: Optional[str] = os.getenv("SORT_ORDER")
        self.download_path: Optional[str] = os.getenv("DOWNLOAD_PATH", "~/Downloads")
        self.repo_api_base_url: str = os.getenv("COMPOID_REPO_API_URL", "https://www.compoid.com/api")
        self.ai_api_base_url: str = os.getenv("COMPOID_AI_API_URL", "https://api.compoid.com/v1")
        self.upload_server_url: str = os.getenv("COMPOID_UPLOAD_URL", "https://mcps.compoid.com/upload")
        self.ai_model: str = os.getenv("COMPOID_AI_MODEL", "Qwen3.5-27B-FP8")
        
        # API keys: Can be set from env vars (COMPOID_REPO_API_KEY) or HTTP headers (X-Compoid-Repo-Key)
        # HTTP headers take precedence when using MCP proxy with user-specific credentials
        self.repo_api_key: Optional[str] = os.getenv("COMPOID_REPO_API_KEY")
        self.ai_api_key: Optional[str] = os.getenv("COMPOID_AI_API_KEY")
        # mcp-proxy Bearer token — used to authenticate with the upload server
        # Set from the Authorization header on each request by setup_user_keys_from_headers()
        self.proxy_token: Optional[str] = os.getenv("UPLOAD_AUTH_TOKEN")
        
        self.timeout: float = float(os.getenv("COMPOID_TIMEOUT", "30.0"))
        self.max_concurrent_requests: int = int(os.getenv("COMPOID_MAX_CONCURRENT", "10"))
        self.default_page_size: int = int(os.getenv("COMPOID_DEFAULT_PAGE_SIZE", "25"))
        self.max_page_size: int = int(os.getenv("COMPOID_MAX_PAGE_SIZE", "200"))

        # Rate limiting
        self.daily_request_limit: int = int(os.getenv("COMPOID_DAILY_LIMIT", "100000"))

        # Logging
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")
        self.log_api_requests: bool = os.getenv("LOG_API_REQUESTS", "false").lower() == "true"
        self.extract_archive: bool = os.getenv("EXTRACT_ARCHIVE", "false").lower() == "true"

    def validate(self) -> None:
        """Validate configuration."""
        if self.timeout <= 0:
            raise ValueError("COMPOID_TIMEOUT must be positive")

        if self.max_concurrent_requests <= 0:
            raise ValueError("COMPOID_MAX_CONCURRENT must be positive")

        if self.default_page_size <= 0 or self.default_page_size > self.max_page_size:
            raise ValueError(f"COMPOID_DEFAULT_PAGE_SIZE must be between 1 and {self.max_page_size}")

        if self.daily_request_limit <= 0:
            raise ValueError("COMPOID_DAILY_LIMIT must be positive")

    def set_user_api_keys(self, repo_key: Optional[str] = None, ai_key: Optional[str] = None, proxy_token: Optional[str] = None) -> None:
        """Set user-specific API keys from HTTP headers.
        
        This method should be called by the request handler when processing
        requests through MCP proxy with user-specific credentials.
        Sets the repo_api_key, ai_api_key, and proxy_token directly, overriding env var defaults.
        
        Args:
            repo_key: User-specific repository API key from X-Compoid-Repo-Key header
            ai_key: User-specific AI API key from X-Compoid-AI-Key header
            proxy_token: mcp-proxy Bearer token from Authorization header (used for upload server auth)
        """
        if repo_key:
            self.repo_api_key = repo_key
        if ai_key:
            self.ai_api_key = ai_key
        if proxy_token:
            self.proxy_token = proxy_token

    def get_user_agent(self) -> str:
        """Get user agent string for API requests."""
        base = "CompoidMCP/0.1.0"
        return base

# Global config instance
config = CompoidConfig()
