import sys
import json
import asyncio
from starlette.applications import Starlette
from starlette.responses import JSONResponse, HTMLResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
import uvicorn
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def index(request):
    with open("frontend/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

async def analyze(request):
    try:
        data = await request.json()
        
        server_params = StdioServerParameters(
            command=sys.executable,  # Uses the active venv python
            args=["starian/server.py"]
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                result = await session.call_tool("analyze_mr_diff", arguments=data)
                
                if result.isError:
                    return JSONResponse({"error": "Erro na execução da tool MCP"}, status_code=500)
                
                text_content = result.content[0].text
                return JSONResponse({"result": text_content})
                
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

app = Starlette(debug=True, routes=[
    Route("/", index),
    Route("/api/analyze", analyze, methods=["POST"]),
    Mount("/static", app=StaticFiles(directory="frontend"), name="static")
])

if __name__ == "__main__":
    print("Iniciando Test Frontend Proxy (Starlette) em http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
