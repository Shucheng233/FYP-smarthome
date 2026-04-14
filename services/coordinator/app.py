import os
import httpx

from datetime import datetime
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from llm_iot_extractor import LLMIoTExtractor


# LLM API Mode: "local" (Ollama) or "remote" (e.g., OpenAI, Claude, etc.)
LLM_API_MODE = os.getenv("LLM_API_MODE", "").strip().lower()

# Ollama settings (local LLM)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "").strip()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "").strip()

# Remote LLM API settings
REMOTE_LLM_API_KEY = os.getenv("REMOTE_LLM_API_KEY", "").strip()
REMOTE_LLM_API_URL = os.getenv("REMOTE_LLM_API_URL", "").strip()
REMOTE_LLM_MODEL = os.getenv("REMOTE_LLM_MODEL", "").strip()


app = FastAPI(title="FYP Coordinator", version="0.3.0")

# Mount static files for web dashboard
app.mount("/static", StaticFiles(directory="web"), name="web")


class IoTCommandRequest(BaseModel):
    prompt: str


# 初始化 extractor
try:
    extractor = LLMIoTExtractor()
except Exception as e:
    extractor = None
    print(f"[startup] failed to initialize LLMIoTExtractor: {e}")


@app.get("/")
def root():
    return FileResponse("web/index.html", media_type="text/html")


@app.get("/health", tags=["health"])
def health():
    return {
        "status": "ok",
        "service": "coordinator",
        "llm_api_mode": LLM_API_MODE,
        "ollama_base_url": OLLAMA_BASE_URL if LLM_API_MODE == "local" else None,
        "ollama_model": OLLAMA_MODEL if LLM_API_MODE == "local" else None,
        "remote_llm_model": REMOTE_LLM_MODEL if LLM_API_MODE == "remote" else None,
        "extractor_ready": extractor is not None,
    }


@app.post("/iot/command", tags=["iot"])
def iot_command(req: IoTCommandRequest):
    """
    Convert natural-language smart-home input into validated JSON commands.
    """
    if extractor is None:
        raise HTTPException(
            status_code=500,
            detail="LLM extractor is not initialized. Check startup logs, .env, and iot_command_format_v3.md.",
        )

    prompt = (req.prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    try:
        commands = extractor.extract(prompt)
        return {
            "prompt": prompt,
            "commands": commands,
            "count": len(commands),
            "llm_api_mode": LLM_API_MODE,
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"IoT command extraction failed: {str(e)}")


# Keep old /llm for compatibility
@app.post("/llm", tags=["llm"])
def llm(req: IoTCommandRequest):
    # For backward compatibility, treat as IoT command extraction
    return iot_command(req)


# --- Web (Dashboard) ---
# 把 coordinator/web 当成静态资源目录（index.html/app.js/style.css）

@app.websocket("/ws/device")
async def websocket_device(websocket: WebSocket):
    await websocket.accept()
    client = websocket.client
    print(f"[{datetime.now()}] device connected: {client}")

    try:
        while True:
            data = await websocket.receive_text()
            print(f"[{datetime.now()}] received from device: {data}")

            reply = f"ack: {data}"
            await websocket.send_text(reply)
            print(f"[{datetime.now()}] sent to device: {reply}")

    except WebSocketDisconnect:
        print(f"[{datetime.now()}] device disconnected: {client}")
    except Exception as e:
        print(f"[{datetime.now()}] websocket error: {e}")