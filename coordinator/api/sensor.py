from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

router = APIRouter(prefix="/sensor", tags=["sensor"])

# 先用内存保存“最新传感器数据”（后面换成 MQTT/DB 都行）
LATEST = {
    "temperature": None,
    "humidity": None,
    "co2": None,
    "updated_at": None,
}

class SensorIn(BaseModel):
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    co2: Optional[float] = None

@router.get("/latest")
def latest():
    return {"status": "ok", "data": LATEST}

@router.post("/update")
def update(payload: SensorIn):
    # Pi/ESP 以后就往这个接口 POST 数据（或 MQTT 转进来）
    if payload.temperature is not None:
        LATEST["temperature"] = payload.temperature
    if payload.humidity is not None:
        LATEST["humidity"] = payload.humidity
    if payload.co2 is not None:
        LATEST["co2"] = payload.co2

    LATEST["updated_at"] = datetime.utcnow().isoformat() + "Z"
    return {"status": "ok", "data": LATEST}
