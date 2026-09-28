from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.models.chat import ChatRequest, ChatResponse
from app.services.claude_service import claude_service
from app.services.search_service import search_service
from app.api.auth import get_current_user
from app.core.config import settings
from typing import Optional
from datetime import date
import json
import logging

logger = logging.getLogger(__name__)

# --- Usage limits (in-memory, per day) ---
_daily_usage: dict = {}  # "username:YYYY-MM-DD" -> count
_MAX_USAGE_ENTRIES = 10000


def _cleanup_usage():
    """Remove entries from previous days"""
    if len(_daily_usage) > _MAX_USAGE_ENTRIES:
        today = str(date.today())
        stale = [k for k in _daily_usage if not k.endswith(today)]
        for k in stale:
            del _daily_usage[k]


def get_user_usage(username: str) -> int:
    """Get today's message count for a user"""
    key = f"{username}:{date.today()}"
    return _daily_usage.get(key, 0)


def record_usage(username: str):
    """Record a message for the user"""
    _cleanup_usage()
    key = f"{username}:{date.today()}"
    _daily_usage[key] = _daily_usage.get(key, 0) + 1


def check_usage_limit(user: dict):
    """Raise 429 if user exceeded daily limit. Admins are unlimited."""
    limit = settings.DAILY_MESSAGE_LIMIT
    if limit <= 0 or user["role"] == "admin":
        return
    used = get_user_usage(user["username"])
    if used >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Límite diario alcanzado ({limit} mensajes). Volvé mañana."
        )

router = APIRouter(prefix="/api/chat", tags=["Chat"])


class StreamRequest(BaseModel):
    query: str
    limit: int = 5
    similarity_threshold: float = 0.2
    document_type: Optional[str] = None
    obra: Optional[str] = None
    fecha_desde: Optional[str] = None
    fecha_hasta: Optional[str] = None

    @property
    def safe_query(self) -> str:
        return self.query[:2000].strip() if self.query else ""


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest, user: dict = Depends(get_current_user)):
    """
    Endpoint principal de chat con Claude

    Recibe un mensaje del usuario y retorna la respuesta de Claude
    (sin RAG por ahora, eso viene en pasos posteriores)
    """
    # Limitar historial de conversación
    if request.conversation_history and len(request.conversation_history) > 50:
        request.conversation_history = request.conversation_history[-50:]

    try:
        # Llamar al servicio de Claude
        result = await claude_service.chat(
            message=request.safe_message,
            conversation_history=request.conversation_history
        )

        return ChatResponse(
            response=result["response"],
            model_used=result["model_used"],
            tokens_used=result.get("tokens_used")
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail="Error interno del chat")


@router.get("/usage")
async def get_usage(user: dict = Depends(get_current_user)):
    """Retorna el uso diario del usuario actual"""
    limit = settings.DAILY_MESSAGE_LIMIT
    used = get_user_usage(user["username"])
    is_unlimited = limit <= 0 or user["role"] == "admin"
    return {
        "used": used,
        "limit": limit,
        "remaining": max(0, limit - used) if not is_unlimited else -1,
        "unlimited": is_unlimited
    }


@router.post("/stream")
async def chat_stream(request: StreamRequest, user: dict = Depends(get_current_user)):
    """
    Endpoint de chat con streaming SSE.
    Busca documentos relevantes y retorna la respuesta de Claude en tiempo real.
    """
    check_usage_limit(user)

    if request.limit > 20:
        request.limit = 20
    if not (0.0 <= request.similarity_threshold <= 1.0):
        request.similarity_threshold = 0.2

    record_usage(user["username"])

    # Build optional filters
    filters = {}
    if request.document_type:
        filters["document_type"] = request.document_type
    if request.obra:
        filters["obra"] = request.obra
    if request.fecha_desde:
        filters["fecha_desde"] = request.fecha_desde
    if request.fecha_hasta:
        filters["fecha_hasta"] = request.fecha_hasta

    def event_generator():
        try:
            for chunk in search_service.search_with_context_stream(
                query=request.safe_query,
                limit=request.limit,
                similarity_threshold=request.similarity_threshold,
                **filters
            ):
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': 'Error al generar respuesta'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/test")
async def test_claude(user: dict = Depends(get_current_user)):
    """
    Endpoint de prueba rápida para verificar que Claude funciona
    """
    try:
        response = await claude_service.chat_simple("Di 'Hola, soy Raúl y estoy listo para ayudar a BECHA SA'")
        return {
            "success": True,
            "message": "Claude está funcionando correctamente",
            "test_response": response
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error al probar Claude")
