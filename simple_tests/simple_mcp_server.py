import json
import logging
import os  # Import os module
from typing import Any, Dict, List, Optional, Union

import uvicorn
from fastapi import FastAPI, Request
from pydantic import BaseModel, ValidationError

app = FastAPI()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QueryContext(BaseModel):
    conversation_id: Optional[str] = None
    history: Optional[List[Dict[str, Any]]] = None
    user_preferences: Dict[str, Any] = {}

class QueryParams(BaseModel):
    query: str
    context: Optional[QueryContext] = None
    parameters: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None

class RequestParams(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    id: Union[str, int]
    params: Dict[str, Any]

@app.post("/mcp")
async def mcp_handler(request: Request):
    """
    Processes JSON-RPC 2.0 requests for the MCP server and returns structured responses.
    
    Supports the following methods:
    - "initialize": Returns server metadata including server name, version, and MCP version.
    - "asr_got.query": Processes a query and returns a simulated answer with reasoning trace, graph state, confidence vector, execution time, and session ID.
    - "shutdown": Returns a null result.
    
    Returns a JSON-RPC error response for unsupported methods or if validation or internal errors occur.
    """
    try:
        data = await request.json()
        jsonrpc = data.get("jsonrpc")
        method = data.get("method")
        req_id = data.get("id")
        params = data.get("params", {})

        logger.info(f"Received MCP request: {method}, id: {req_id}")
        logger.debug(f"Params: {json.dumps(params, indent=2)}")

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "server_name": "NexusMind MCP Server",
                    "server_version": "0.1.0",
                    "mcp_version": "2024-11-05"
                }
            }
        elif method == "asr_got.query":
            query = params.get("query", "No query provided")
            # Simulate detailed response with reasoning traces and graph states
            reasoning_trace_summary = "Reasoning trace: Step 1 -> Step 2 -> Step 3"
            graph_state_full = {
                "nodes": [
                    {"id": "n1", "label": "Node 1", "type": "root"},
                    {"id": "n2", "label": "Node 2", "type": "evidence"}
                ],
                "edges": [
                    {"id": "e1", "source": "n1", "target": "n2", "type": "supports"}
                ]
            }
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "answer": f"NexusMind processed your query: {query}",
                    "reasoning_trace_summary": reasoning_trace_summary,
                    "graph_state_full": graph_state_full,
                    "confidence_vector": [0.85, 0.92, 0.78, 0.89],
                    "execution_time_ms": 1250,
                    "session_id": "sample-session-123"
                }
            }
        elif method == "shutdown":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": None
            }
        else:
            logger.warning(f"Unsupported MCP method received: {method}")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method '{method}' not supported"
                }
            }
    except ValidationError as ve:
        logger.warning(f"MCP Validation Error for method {method}: {ve}")
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32602,
                "message": "Invalid parameters.",
                "data": {"details": ve.errors(), "method": method}
            }
        }
    except Exception as e:
        logger.exception(f"Error in MCP endpoint_handler for method {method}: {e}")
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32603,
                "message": f"Internal error: {e!s}"
            }
        }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "0.1.0"}

if __name__ == "__main__":
    logger.info("Starting NexusMind MCP Server...")
    # Determine port from environment variable or default to 8000
    port_str = os.environ.get("PORT")
    server_port = 8000  # Default port
    if port_str and port_str.isdigit():
        server_port = int(port_str)
    else:
        logger.info(f"PORT environment variable not set or invalid, defaulting to {server_port}")

    uvicorn.run(app, host="0.0.0.0", port=server_port)
