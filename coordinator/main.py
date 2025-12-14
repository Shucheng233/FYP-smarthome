import os
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from api.sensor import router as sensor_router
from api.iot import router as iot_router
from api.stt import router as stt_router
from api.tts import router as tts_router

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")

app = FastAPI(title="FYP Coordinator", version="0.2.0")

# --- API Routers ---
app.include_router(sensor_router)
app.include_router(iot_router)
app.include_router(stt_router)
app.include_router(tts_router)

class LLMRequest(BaseModel):
    prompt: str

@app.get("/health", tags=["health"])
def health():
    return {
        "status": "ok",
        "service": "coordinator",
        "ollama_base_url": OLLAMA_BASE_URL,
        "ollama_model": OLLAMA_MODEL,
    }

@app.post("/llm", tags=["llm"])
def llm(req: LLMRequest):
    payload = {"model": OLLAMA_MODEL, "prompt": req.prompt, "stream": False}
    try:
        r = httpx.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        return {"response": data.get("response", ""), "raw": data}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Ollama HTTP error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ollama unreachable: {str(e)}")

# --- Web (Dashboard) ---
# 把 coordinator/web 当成静态资源目录（index.html/app.js/style.css）
app.mount("/static", StaticFiles(directory="web"), name="static")

@app.get("/", include_in_schema=False)
def index():
    return FileResponse("web/index.html")
