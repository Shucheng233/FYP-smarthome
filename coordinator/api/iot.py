from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/iot", tags=["iot"])

class IoTCommand(BaseModel):
    device: str          # e.g. "curtain", "fan", "light"
    action: str          # e.g. "open", "close", "on", "off"
    value: str | None = None  # optional

@router.post("/command")
def command(cmd: IoTCommand):
    # 先做“假执行”闭环：记录命令并返回 ok
    # 后面这里改成 MQTT publish / HTTP call 就行
    return {
        "status": "ok",
        "accepted": True,
        "cmd": cmd.model_dump(),
        "ts": datetime.utcnow().isoformat() + "Z",
        "note": "placeholder (not connected to real devices yet)"
    }
