from fastapi import APIRouter

router = APIRouter(prefix="/tts", tags=["tts"])

@router.get("/status")
def status():
    return {"status": "todo", "service": "tts", "note": "not implemented yet"}
