from fastapi import APIRouter

router = APIRouter(prefix="/stt", tags=["stt"])

@router.get("/status")
def status():
    return {"status": "todo", "service": "stt", "note": "not implemented yet"}
