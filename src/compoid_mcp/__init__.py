"""Compoid MCP Server - A Model Context Protocol server for the Compoid scholarly database."""

def __get_version() -> str:
    try:
        from importlib.metadata import version
        return version("compoid-mcp")
    except Exception:
        return "0.1.1"


__version__ = __get_version()
