"""API de feedback para respuestas del asistente"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Literal
import uuid as _uuid
import logging

from app.services.supabase_service import supabase_service
from app.api.auth import get_current_user, require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/feedback", tags=["Feedback"])


class FeedbackRequest(BaseModel):
    conversation_id: str
    message_index: int
    value: Literal["up", "down"]


@router.post("/")
async def submit_feedback(req: FeedbackRequest, user: dict = Depends(get_current_user)):
    """Guarda o actualiza el feedback de un mensaje del asistente"""
    try:
        _uuid.UUID(req.conversation_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="ID inválido")

    if req.message_index < 0:
        raise HTTPException(status_code=400, detail="Índice inválido")

    try:
        client = supabase_service.get_client()
        # Upsert: actualiza si ya existe feedback del mismo usuario para ese mensaje
        client.table("message_feedback").upsert({
            "conversation_id": req.conversation_id,
            "message_index": req.message_index,
            "feedback": req.value,
            "username": user["username"]
        }, on_conflict="conversation_id,message_index,username").execute()
        return {"success": True}
    except Exception as e:
        logger.error(f"Feedback error: {e}")
        raise HTTPException(status_code=500, detail="Error al guardar feedback")


@router.get("/stats")
async def get_feedback_stats(admin: dict = Depends(require_admin)):
    """Estadísticas de feedback (solo admin)"""
    try:
        client = supabase_service.get_client()
        result = client.table("message_feedback").select("feedback").execute()
        up = sum(1 for r in result.data if r["feedback"] == "up")
        down = sum(1 for r in result.data if r["feedback"] == "down")
        return {"success": True, "up": up, "down": down, "total": len(result.data)}
    except Exception as e:
        logger.error(f"Feedback stats error: {e}")
        return {"success": True, "up": 0, "down": 0, "total": 0}
