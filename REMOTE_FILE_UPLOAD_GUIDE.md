# Remote File Upload via MCP Proxy

## Overview

The Compoid MCP Server supports file uploads from remote clients via the MCP proxy streamable HTTP transport. Three upload paths are available depending on your use case.

## Architecture

```
Remote Client (laptop)
     │
     │  HTTPS  (via mcp-proxy at mcps.compoid.com)
     ▼
MCP Server  (uvicorn  127.0.0.1:8088/mcp)
     │
     │  HTTP POST to config.upload_server_url
     │  (default: https://mcps.compoid.com/upload)
     ▼
Upload Server  (FastAPI  192.168.0.213:8088/upload)
     │
     ▼
/projects/uploads/<uuid>.upload
```

## Upload Options

### Option 1 — `Compoid_upload_file` MCP Tool (recommended for remote clients)

The dedicated upload tool. Accepts a **data URI**, saves the file server-side via the upload server, and returns a `/projects/uploads/...` path that is passed directly to `Compoid_create_record` or `Compoid_update_record`.

**Two-step flow:**

```
Step 1: Compoid_upload_file(file_data="data:<mime>;base64,<data>", filename="doc.odt")
        → returns: "Server path: /projects/uploads/abc123.upload"

Step 2: Compoid_create_record(file_upload="/projects/uploads/abc123.upload", ...)
        → record created
```

**What to say to the AI assistant:**

> *"Create a new Compoid record with `/home/username/Documents/GLM-4.5V_CLAUDE.odt`, community `<id>`, creators `[...]`"*

The assistant will automatically read the file, encode it as a data URI, call `Compoid_upload_file`, then call `Compoid_create_record` with the returned server path. **No manual base64 conversion needed.**

**Manual curl equivalent (for testing):**

```bash
# Upload directly to the upload server via mcp-proxy
curl -X POST https://mcps.compoid.com/upload \
  --data-binary @/home/username/Documents/GLM-4.5V_CLAUDE.odt

# Returns: {"file_path": "/projects/uploads/abc123.upload", "size": ..., "success": true}

# Use the returned path in Compoid_create_record via MCP
```

---

### Option 2 — Data URI directly in `Compoid_create_record`

Pass `file_upload` as a data URI straight to `Compoid_create_record`. Skips the separate upload step — useful for smaller files where you want a single tool call.

```
file_upload = "data:image/png;base64,iVBORw0KGgo..."
```

`create_record` in `tools.py` detects the `data:` prefix and routes it through `_handle_file_input()` in `client.py`, which decodes it to a temp file and cleans up after upload.

---

### Option 3 — Server-side path (`/projects/...`)

For files already on the MCP server filesystem. Pass the path directly — no encoding, no temp files.

```
file_upload = "/projects/uploads/myfile.png"
```

This is also the path returned by `Compoid_upload_file` (Option 1), making the two-step flow seamless.

---

## `file_upload` Routing Logic (in `tools.py`)

```
file_upload value
├─ starts with "data:"        → Option 2: data URI, decoded via _handle_file_input()
├─ starts with "/projects"    → Option 3: server-side path, used directly
└─ anything else              → Error: file not accessible on server
                                 Hint: use Compoid_upload_file first (Option 1)
```

---

## Configuration

The upload server URL is configured via the `COMPOID_UPLOAD_URL` environment variable in `config.py`:

```python
self.upload_server_url: str = os.getenv("COMPOID_UPLOAD_URL", "https://mcps.compoid.com/upload")
```

| Env Var | Default | Description |
|---------|---------|-------------|
| `COMPOID_UPLOAD_URL` | `https://mcps.compoid.com/upload` | Upload server endpoint used by `Compoid_upload_file` |

**`.env` example:**
```bash
# Production (default — via mcp-proxy)
COMPOID_UPLOAD_URL=https://mcps.compoid.com/upload

# Local/dev (direct LAN access)
COMPOID_UPLOAD_URL=http://192.168.0.213:8088/upload
```

---

## `Compoid_upload_file` Tool Reference

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_data` | string | ✅ | Data URI: `data:<mime>;base64,<base64-data>` |
| `filename` | string | ❌ | Original filename (e.g. `photo.png`) — passed as `X-Filename` header for logging |

**Returns:**

```
File uploaded successfully.
Server path: /projects/uploads/abc123def456.upload
Size: 204800 bytes

Use this path as file_upload in Compoid_create_record or Compoid_update_record.
```

---

## Key Features

✅ **No manual base64 needed** — AI assistant handles encoding automatically  
✅ **Three upload paths** — dedicated upload tool, data URI, or direct server path  
✅ **No hardcoded IPs** — upload URL configured via `COMPOID_UPLOAD_URL` env var  
✅ **Backward compatible** — existing `/projects/` paths still work  
✅ **Automatic cleanup** — temp files (from data URI path) removed after upload  
✅ **MIME type detection** — works with images, videos, documents, etc.  
✅ **Secure transport** — HTTPS via mcp-proxy, upload server is LAN-only  

---

## Troubleshooting

**Q: I passed a local path like `/home/username/file.odt` and got an error.**  
A: The MCP server runs on a different machine and cannot read your local filesystem. Ask the AI assistant to upload the file using `Compoid_upload_file` first, then pass the returned `/projects/uploads/...` path to `Compoid_create_record`.

**Q: How do I know if my data URI was recognized?**  
A: Enable debug logging: `config.log_api_requests = True`  
Look for: `"Created temporary file from base64 content: /tmp/..."`

**Q: What if the file is very large?**  
A: Base64 encoding increases size by ~33%. For files >500 MB consider:
- Compressing before encoding
- Placing the file directly on the server under `/projects/` and using Option 3

**Q: Does `Compoid_upload_file` preserve the original filename?**  
A: The server saves with a UUID name (e.g. `abc123.upload`). The `filename` parameter is passed as an `X-Filename` header for context — it does not affect the saved path.

**Q: Does this work with the MCP proxy?**  
A: Yes. All three options route through `mcps.compoid.com:8087 → 127.0.0.1:8088/mcp`.

---

## Security Considerations

⚠️ **Important**
- Data URI content is transmitted as text over the MCP protocol
- Ensure your MCP proxy connection uses HTTPS/TLS — it does by default via mcp-proxy
- Temporary files are created in the system temp directory (`/tmp`) and cleaned up after upload
- The upload server (`192.168.0.213:8088`) is LAN-only; external access goes through mcp-proxy
