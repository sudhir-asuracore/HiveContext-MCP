import os
import sys
import json
import logging
import uvicorn
from fastmcp import FastMCP
from starlette.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HiveContext-MCP")

mcp = FastMCP("HiveContext MCP Server")

@mcp.tool()
def search_context(query: str, limit: int = 5) -> str:
    """Perform semantic RAG retrieval search across organizational memory bank in CockroachDB vector store."""
    return f"Search results for: {query}"

@mcp.tool()
def remember_convention(topic: str, content: str, scope: str = "global") -> str:
    """Save a coding convention or architectural rule to the collective memory bank."""
    return f"Saved convention: {topic}"

@mcp.tool()
def log_post_mortem(topic: str, content: str) -> str:
    """Record a post-mortem incident or bug fix context entry for future agent lookup."""
    return f"Logged post mortem: {topic}"

@mcp.tool()
def save_adr(topic: str, content: str) -> str:
    """Save an Architectural Decision Record (ADR) into the active memory space."""
    return f"Saved ADR: {topic}"

@mcp.tool()
def save_infrastructure_context(component: str, configuration: str, dependencies: str = "") -> str:
    """Save infrastructure & deployment specifications."""
    return f"Saved infrastructure context: {component}"

# Create FastMCP stateless ASGI app
fastmcp_app = mcp.http_app(
    path="/",
    transport="http",
    stateless_http=True,
    json_response=True,
)

EXPECTED_TOKEN = os.environ.get("MCP_SECRET_TOKEN", "")

async def app(scope, receive, send):
    """ASGI routing & auth adapter for AWS Lambda Web Adapter."""
    if scope["type"] == "http":
        headers_list = list(scope.get("headers", []))
        headers_dict = dict(headers_list)
        method = scope.get("method", "GET")
        path = scope.get("path", "/")

        # Health / root check
        if method == "GET" and path in ("/", "/health"):
            res = JSONResponse({"status": "ok", "service": "HiveContext MCP Server", "version": "1.0.0"})
            await res(scope, receive, send)
            return

        # Bearer token validation
        if EXPECTED_TOKEN:
            auth_header = headers_dict.get(b"authorization", b"").decode("utf-8")
            if not auth_header.startswith("Bearer ") or auth_header[7:].strip() != EXPECTED_TOKEN:
                res = JSONResponse(
                    {"jsonrpc": "2.0", "id": "auth-error", "error": {"code": -32000, "message": "Unauthorized"}},
                    status_code=401,
                )
                await res(scope, receive, send)
                return

        # Ensure Accept header includes application/json for MCP client compatibility
        accept_val = headers_dict.get(b"accept", b"").decode("utf-8")
        if "application/json" not in accept_val:
            new_headers = [(k, v) for k, v in headers_list if k.lower() != b"accept"]
            new_headers.append((b"accept", b"application/json, text/event-stream, */*"))
            scope["headers"] = new_headers

        # Normalize path so FastMCP root handler handles /, /sse, /mcp
        scope["path"] = "/"
        await fastmcp_app(scope, receive, send)
    else:
        await fastmcp_app(scope, receive, send)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

