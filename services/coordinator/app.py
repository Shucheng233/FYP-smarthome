import os
import json
import httpx

from datetime import datetime
from typing import List
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from llm_iot_extractor import LLMIoTExtractor


# =====================================================
# 一、LLM 配置
# =====================================================

# LLM API Mode: "local" (Ollama) or "remote" (e.g., OpenAI, Claude, etc.)
LLM_API_MODE = os.getenv("LLM_API_MODE", "").strip().lower()

# Ollama settings (local LLM)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "").strip()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "").strip()

# Remote LLM API settings
REMOTE_LLM_API_KEY = os.getenv("REMOTE_LLM_API_KEY", "").strip()
REMOTE_LLM_API_URL = os.getenv("REMOTE_LLM_API_URL", "").strip()
REMOTE_LLM_MODEL = os.getenv("REMOTE_LLM_MODEL", "").strip()


app = FastAPI(title="FYP Coordinator", version="0.4.0")

# Mount static files for web dashboard
app.mount("/static", StaticFiles(directory="web"), name="web")


class IoTCommandRequest(BaseModel):
    prompt: str


# =====================================================
# 二、全局：保存已连接的 ESP32 WebSocket
# =====================================================
# 改动功能：
# 1. 以前 /ws/device 只是收到消息就 reply
# 2. 现在把连接保存起来，后面 /iot/command 可以主动发命令给 ESP32
connected_devices: List[WebSocket] = []


# =====================================================
# 三、初始化 extractor
# =====================================================
try:
    extractor = LLMIoTExtractor()
except Exception as e:
    extractor = None
    print(f"[startup] failed to initialize LLMIoTExtractor: {e}")


# =====================================================
# 四、工具函数：广播 commands 到已连接设备
# =====================================================
async def broadcast_commands_to_devices(commands):
    """
    把解析后的 commands 广播给所有已连接的 ESP32。
    当前发送格式：直接发送 JSON 数组
    因为你现在 ESP32 代码已经兼容 JSON 数组格式。
    """
    if not connected_devices:
        print(f"[{datetime.now()}] [WS] no connected device, skip sending")
        return 0

    message = json.dumps(commands, ensure_ascii=False)
    dead_connections = []

    for ws in connected_devices:
        try:
            await ws.send_text(message)
            print(f"[{datetime.now()}] [WS] sent commands to device: {message}")
        except Exception as e:
            print(f"[{datetime.now()}] [WS] failed to send to device: {e}")
            dead_connections.append(ws)

    # 清理失效连接
    for ws in dead_connections:
        if ws in connected_devices:
            connected_devices.remove(ws)

    return len(connected_devices)


# =====================================================
# 五、基础接口
# =====================================================
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
        "connected_devices": len(connected_devices),  # 改动功能：health 里能直接看到当前设备连接数
    }


# =====================================================
# 六、IoT Command 接口
# =====================================================
@app.post("/iot/command", tags=["iot"])
async def iot_command(req: IoTCommandRequest):
    """
    Convert natural-language smart-home input into validated JSON commands.
    改动功能：
    1. 以前这里只返回 commands 给网页
    2. 现在会在返回网页的同时，把 commands 发给 ESP32
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
        # 第一步：LLM 提取 JSON commands
        commands = extractor.extract(prompt)

        print(f"[{datetime.now()}] [IOT] prompt: {prompt}")
        print(f"[{datetime.now()}] [IOT] extracted commands: {commands}")

        # 第二步：把 commands 发给已连接设备
        sent_to = await broadcast_commands_to_devices(commands)

        # 第三步：继续返回给网页显示
        return {
            "prompt": prompt,
            "commands": commands,
            "count": len(commands),
            "llm_api_mode": LLM_API_MODE,
            "sent_to_devices": sent_to,   # 改动功能：网页返回里能看到发给了几个设备
        }

    except Exception as e:
        raise HTTPException(status_code=502, detail=f"IoT command extraction failed: {str(e)}")


# Keep old /llm for compatibility
@app.post("/llm", tags=["llm"])
async def llm(req: IoTCommandRequest):
    # For backward compatibility, treat as IoT command extraction
    return await iot_command(req)


# =====================================================
# 七、设备 WebSocket
# =====================================================
@app.websocket("/ws/device")
async def websocket_device(websocket: WebSocket):
    await websocket.accept()
    client = websocket.client

    # 改动功能：保存连接
    connected_devices.append(websocket)
    print(f"[{datetime.now()}] [WS] device connected: {client}")
    print(f"[{datetime.now()}] [WS] connected device count: {len(connected_devices)}")

    try:
        while True:
            data = await websocket.receive_text()
            print(f"[{datetime.now()}] [WS] received from device: {data}")

            # 保留你原来的 hello -> ack 兼容逻辑
            reply = f"ack: {data}"
            await websocket.send_text(reply)
            print(f"[{datetime.now()}] [WS] sent to device: {reply}")

    except WebSocketDisconnect:
        print(f"[{datetime.now()}] [WS] device disconnected: {client}")
        if websocket in connected_devices:
            connected_devices.remove(websocket)
        print(f"[{datetime.now()}] [WS] connected device count: {len(connected_devices)}")

    except Exception as e:
        print(f"[{datetime.now()}] [WS] websocket error: {e}")
        if websocket in connected_devices:
            connected_devices.remove(websocket)
        print(f"[{datetime.now()}] [WS] connected device count: {len(connected_devices)}")
