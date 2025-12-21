import os
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from fastapi.responses import FileResponse

from pydantic import BaseModel

#from api.sensor import router as sensor_router
#from api.iot import router as iot_router
#from api.stt import router as stt_router
#from api.tts import router as tts_router

# LLM API Mode: "local" (Ollama) or "remote" (e.g., OpenAI, Claude, etc.)
LLM_API_MODE = os.getenv("LLM_API_MODE")
# Ollama settings (local LLM)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")

# Remote LLM API settings
REMOTE_LLM_API_KEY = os.getenv("REMOTE_LLM_API_KEY")
REMOTE_LLM_API_URL = os.getenv("REMOTE_LLM_API_URL")
REMOTE_LLM_MODEL = os.getenv("REMOTE_LLM_MODEL")

# TODO: Add system prompt for IoT command generation

app = FastAPI(title="FYP Coordinator", version="0.2.0")

# Mount static files for web dashboard
app.mount("/static", StaticFiles(directory="web"), name="web")

# --- API Routers ---
#app.include_router(sensor_router)
#app.include_router(iot_router)
#app.include_router(stt_router)
#app.include_router(tts_router)

class IoTCommandRequest(BaseModel):
    prompt: str

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
    }

@app.post("/iot/command", tags=["iot"])
def iot_command(req: IoTCommandRequest):
    # TODO: Implement with system prompt
    if LLM_API_MODE == "local":
        # Use local Ollama
        payload = {"model": OLLAMA_MODEL, "prompt": f"Parse this into IoT commands: {req.prompt}", "stream": False}
        try:
            r = httpx.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload, timeout=120)
            r.raise_for_status()
            data = r.json()
            response = data.get("response", "")
            # TODO: Parse JSON response
            return {"response": response, "raw": data}
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Ollama error: {str(e)}")
    elif LLM_API_MODE == "remote":
        # Use remote LLM API
        try:
            headers = {"Authorization": f"Bearer {REMOTE_LLM_API_KEY}"}
            payload = {
                "model": REMOTE_LLM_MODEL,
                "messages": [{"role": "user", "content": f"Parse this into IoT commands: {req.prompt}"}],
            }
            r = httpx.post(REMOTE_LLM_API_URL, json=payload, headers=headers, timeout=120)
            r.raise_for_status()
            data = r.json()
            response = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            # TODO: Parse JSON response
            return {"response": response, "raw": data}
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Remote LLM error: {str(e)}")
    else:
        raise HTTPException(status_code=400, detail=f"LLM_API_MODE not configured: {LLM_API_MODE}. Please set LLM_API_MODE in environment variables.")

# Keep old /llm for compatibility
@app.post("/llm", tags=["llm"])
def llm(req: IoTCommandRequest):
    # For backward compatibility, treat as IoT command
    return iot_command(req)

# --- Web (Dashboard) ---
# 把 coordinator/web 当成静态资源目录（index.html/app.js/style.css）

