import os
import sys
import json
import logging
import requests
import psycopg2
import uvicorn
from fastmcp import FastMCP
from starlette.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HiveContext-MCP")

# Database & Embedding configuration
DATABASE_URL = os.environ.get("DATABASE_URL", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "gemini-embedding-001")
EXPECTED_TOKEN = os.environ.get("MCP_SECRET_TOKEN", "")

def get_db_connection():
    if not DATABASE_URL:
        return None
    # Normalize connection string for CockroachDB
    conn_str = DATABASE_URL.replace("&sslrootcert=system", "").replace("?sslrootcert=system&", "?")
    if "sslmode=" not in conn_str:
        conn_str += "?sslmode=require" if "?" not in conn_str else "&sslmode=require"
    conn = psycopg2.connect(conn_str)
    conn.autocommit = True
    return conn

def get_embedding(text: str) -> list[float] | None:
    if not GEMINI_API_KEY:
        return None
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{EMBEDDING_MODEL}:embedContent?key={GEMINI_API_KEY}"
        payload = {
            "model": f"models/{EMBEDDING_MODEL}",
            "content": {"parts": [{"text": text[:4000]}]}
        }
        res = requests.post(url, json=payload, timeout=8)
        if res.ok:
            data = res.json()
            return data.get("embedding", {}).get("values")
        logger.warning(f"Embedding error ({res.status_code}): {res.text}")
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
    return None

def insert_memory(context_type: str, topic: str, content: str, scope: str = "global", project_name: str = "") -> dict:
    try:
        conn = get_db_connection()
        if not conn:
            return {"success": False, "error": "Database not configured"}
        
        embed = get_embedding(f"{topic}\n{content}")
        embed_str = ("[" + ",".join(str(x) for x in embed) + "]") if embed else None
        
        with conn.cursor() as cur:
            if embed_str:
                cur.execute("""
                    INSERT INTO hive_context 
                      (context_type, topic, content, embedding, embedding_provider, embedding_model, embedding_dimensions, author, author_role, status, scope, project_name)
                    VALUES 
                      (%s, %s, %s, %s::vector, 'gemini', %s, %s, 'agent', 'agent', 'pending', %s, %s)
                    RETURNING id, topic, status, created_at;
                """, (context_type, topic, content, embed_str, EMBEDDING_MODEL, len(embed), scope, project_name or None))
            else:
                cur.execute("""
                    INSERT INTO hive_context 
                      (context_type, topic, content, author, author_role, status, scope, project_name)
                    VALUES 
                      (%s, %s, %s, 'agent', 'agent', 'pending', %s, %s)
                    RETURNING id, topic, status, created_at;
                """, (context_type, topic, content, scope, project_name or None))
            
            row = cur.fetchone()
            conn.close()
            return {"success": True, "id": str(row[0]), "topic": row[1], "status": row[2]}
    except Exception as e:
        logger.error(f"Error inserting memory: {e}")
        return {"success": False, "error": str(e)}

mcp = FastMCP("HiveContext MCP Server")

@mcp.tool()
def search_context(query: str, limit: int = 5) -> str:
    """Perform semantic RAG retrieval search across organizational memory bank in CockroachDB vector store."""
    try:
        conn = get_db_connection()
        if not conn:
            return json.dumps({"error": "Database connection unavailable", "query": query, "results": []})
        
        embed = get_embedding(query)
        with conn.cursor() as cur:
            if embed:
                embed_str = "[" + ",".join(str(x) for x in embed) + "]"
                cur.execute("""
                    SELECT id, topic, context_type, content, scope, project_name, 1 - (embedding <=> %s::vector) AS similarity, created_at
                    FROM hive_context
                    WHERE status IN ('approved', 'auto_approved') AND deleted_at IS NULL
                    ORDER BY embedding <=> %s::vector ASC
                    LIMIT %s;
                """, (embed_str, embed_str, limit))
            else:
                cur.execute("""
                    SELECT id, topic, context_type, content, scope, project_name, 1.0 AS similarity, created_at
                    FROM hive_context
                    WHERE status IN ('approved', 'auto_approved') AND deleted_at IS NULL
                    ORDER BY created_at DESC
                    LIMIT %s;
                """, (limit,))
            
            rows = cur.fetchall()
            conn.close()
            
            results = [
                {
                    "id": str(r[0]),
                    "topic": r[1],
                    "context_type": r[2],
                    "content": r[3],
                    "scope": r[4],
                    "project_name": r[5],
                    "similarity": round(float(r[6]), 4) if r[6] is not None else 0.0,
                    "created_at": str(r[7]),
                }
                for r in rows
            ]
            return json.dumps({"query": query, "count": len(results), "results": results})
    except Exception as e:
        logger.error(f"search_context error: {e}")
        return json.dumps({"error": str(e), "query": query, "results": []})

@mcp.tool()
def remember_convention(topic: str, content: str, scope: str = "global") -> str:
    """Save a coding convention or architectural rule to the collective memory bank."""
    res = insert_memory("convention", topic, content, scope=scope)
    return json.dumps(res)

@mcp.tool()
def log_post_mortem(topic: str, content: str) -> str:
    """Record a post-mortem incident or bug fix context entry for future agent lookup."""
    res = insert_memory("post_mortem", topic, content, scope="global")
    return json.dumps(res)

@mcp.tool()
def save_adr(topic: str, content: str) -> str:
    """Save an Architectural Decision Record (ADR) into the active memory space."""
    res = insert_memory("architecture_decision", topic, content, scope="global")
    return json.dumps(res)

@mcp.tool()
def save_infrastructure_context(component: str, configuration: str, dependencies: str = "") -> str:
    """Save infrastructure & deployment specifications."""
    combined_content = f"Configuration:\n{configuration}\n\nDependencies:\n{dependencies}" if dependencies else configuration
    res = insert_memory("infrastructure_context", component, combined_content, scope="global")
    return json.dumps(res)

# Create FastMCP stateless ASGI app
fastmcp_app = mcp.http_app(
    path="/",
    transport="http",
    stateless_http=True,
    json_response=True,
)

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


