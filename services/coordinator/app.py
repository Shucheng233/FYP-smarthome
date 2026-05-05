import asyncio
import json
import os
from collections import deque
from datetime import datetime
from typing import Any, Deque, Dict, List

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from llm_iot_extractor import LLMIoTExtractor


LLM_API_MODE = os.getenv("LLM_API_MODE", "").strip().lower()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "").strip()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "").strip()
REMOTE_LLM_MODEL = os.getenv("REMOTE_LLM_MODEL", "").strip()

app = FastAPI(title="FYP Coordinator", version="0.5.0")
app.mount("/static", StaticFiles(directory="web"), name="web")


class IoTCommandRequest(BaseModel):
    prompt: str


connected_devices: List[WebSocket] = []
dashboard_clients: List[WebSocket] = []
EVENT_LOG: Deque[Dict[str, Any]] = deque(maxlen=500)
LAST_DEVICE_STATE: Dict[str, Any] = {}


try:
    extractor = LLMIoTExtractor()
except Exception as e:
    extractor = None
    print(f"[startup] failed to initialize LLMIoTExtractor: {e}")


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def add_event(source: str, level: str, message: str, data: Any = None) -> Dict[str, Any]:
    event = {
        "time": now_iso(),
        "source": source,
        "level": level,
        "message": message,
        "data": data,
    }
    EVENT_LOG.append(event)
    print(f"[{event['time']}] [{source}] [{level}] {message}")
    if data is not None:
        print(f"[{event['time']}] [{source}] data: {data}")
    return event


async def broadcast_dashboard(payload: Dict[str, Any]) -> None:
    if not dashboard_clients:
        return

    text = json.dumps(payload, ensure_ascii=False)
    dead_clients: List[WebSocket] = []

    for ws in dashboard_clients:
        try:
            await ws.send_text(text)
        except Exception:
            dead_clients.append(ws)

    for ws in dead_clients:
        if ws in dashboard_clients:
            dashboard_clients.remove(ws)


async def push_event(source: str, level: str, message: str, data: Any = None) -> Dict[str, Any]:
    event = add_event(source, level, message, data)
    await broadcast_dashboard({"type": "event", "event": event})
    return event


def update_state_from_device_payload(payload: Dict[str, Any]) -> None:
    state = payload.get("state")
    if isinstance(state, dict):
        LAST_DEVICE_STATE.clear()
        LAST_DEVICE_STATE.update(state)


async def broadcast_commands_to_devices(commands: List[Dict[str, Any]]) -> int:
    if not connected_devices:
        await push_event("WS", "WARN", "No connected ESP32 device. Command was not sent.", commands)
        return 0

    message = json.dumps(commands, ensure_ascii=False)
    dead_connections: List[WebSocket] = []
    sent_count = 0

    for ws in connected_devices:
        try:
            await ws.send_text(message)
            sent_count += 1
            await push_event("WS", "INFO", "Sent command array to ESP32", commands)
        except Exception as e:
            dead_connections.append(ws)
            await push_event("WS", "ERROR", f"Failed to send command to ESP32: {e}")

    for ws in dead_connections:
        if ws in connected_devices:
            connected_devices.remove(ws)

    return sent_count


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
        "connected_devices": len(connected_devices),
        "dashboard_clients": len(dashboard_clients),
        "event_count": len(EVENT_LOG),
    }


@app.get("/events", tags=["dashboard"])
def events():
    return {"events": list(EVENT_LOG)}


@app.get("/device/state", tags=["dashboard"])
def device_state():
    return {"state": LAST_DEVICE_STATE}


@app.post("/iot/command", tags=["iot"])
async def iot_command(req: IoTCommandRequest):
    if extractor is None:
        raise HTTPException(
            status_code=500,
            detail="LLM extractor is not initialized. Check startup logs, .env, and iot_command_format_v3.md.",
        )

    prompt = (req.prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    try:
        await push_event("WEB", "INFO", f"Prompt received: {prompt}")
        commands = extractor.extract(prompt)
        await push_event("IOT", "INFO", "Extracted validated commands", commands)
        sent_to = await broadcast_commands_to_devices(commands)

        response = {
            "prompt": prompt,
            "commands": commands,
            "count": len(commands),
            "llm_api_mode": LLM_API_MODE,
            "sent_to_devices": sent_to,
        }
        await broadcast_dashboard({"type": "command_response", "response": response})
        return response

    except Exception as e:
        await push_event("IOT", "ERROR", f"IoT command extraction failed: {e}")
        raise HTTPException(status_code=502, detail=f"IoT command extraction failed: {str(e)}")


@app.post("/llm", tags=["llm"])
async def llm(req: IoTCommandRequest):
    return await iot_command(req)


@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    await websocket.accept()
    dashboard_clients.append(websocket)

    await websocket.send_text(
        json.dumps(
            {
                "type": "snapshot",
                "health": health(),
                "events": list(EVENT_LOG),
                "state": LAST_DEVICE_STATE,
            },
            ensure_ascii=False,
        )
    )

    try:
        while True:
            # Keep the connection open. Browser can send ping text if needed.
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in dashboard_clients:
            dashboard_clients.remove(websocket)
    except Exception:
        if websocket in dashboard_clients:
            dashboard_clients.remove(websocket)


@app.websocket("/ws/device")
async def websocket_device(websocket: WebSocket):
    await websocket.accept()
    client = websocket.client
    connected_devices.append(websocket)

    await push_event("WS", "INFO", f"ESP32 connected: {client}")
    await broadcast_dashboard({"type": "health", "health": health()})

    try:
        while True:
            data = await websocket.receive_text()

            try:
                payload = json.loads(data)
                update_state_from_device_payload(payload)
                await push_event("ESP32", "INFO", "Message received from ESP32", payload)
                await broadcast_dashboard({"type": "device_message", "message": payload})
                if LAST_DEVICE_STATE:
                    await broadcast_dashboard({"type": "state", "state": LAST_DEVICE_STATE})
            except json.JSONDecodeError:
                await push_event("ESP32", "INFO", f"Text received from ESP32: {data}")

            # Keep compatibility with current ESP32 code. ESP32 ignores text starting with ack:.
            await websocket.send_text(f"ack: {data}")

    except WebSocketDisconnect:
        await push_event("WS", "WARN", f"ESP32 disconnected: {client}")
        if websocket in connected_devices:
            connected_devices.remove(websocket)
        await broadcast_dashboard({"type": "health", "health": health()})

    except Exception as e:
        await push_event("WS", "ERROR", f"ESP32 websocket error: {e}")
        if websocket in connected_devices:
            connected_devices.remove(websocket)
        await broadcast_dashboard({"type": "health", "health": health()})
