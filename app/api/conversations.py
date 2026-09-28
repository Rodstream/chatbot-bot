"""API para gestión de conversaciones (por usuario)"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Literal
from datetime import datetime, timezone
import asyncio
import uuid as _uuid
from app.services.supabase_service import supabase_service
from app.api.auth import get_current_user
import re


def _validate_uuid(value: str) -> str:
    """Valida que el string sea un UUID válido"""
    try:
        _uuid.UUID(value)
        return value
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="ID inválido")

router = APIRouter(prefix="/api/conversations", tags=["Conversations"])


class MessageCreate(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    sources: Optional[List] = []

    @property
    def safe_content(self) -> str:
        return self.content[:10000].strip() if self.content else ""


@router.get("/")
async def list_conversations(user: dict = Depends(get_current_user)):
    """Lista las conversaciones del usuario actual"""
    try:
        client = supabase_service.get_client()
        result = client.table("conversations") \
            .select("*") \
            .eq("username", user["username"]) \
            .order("updated_at", desc=True) \
            .limit(100) \
            .execute()

        return {"success": True, "conversations": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error interno")


@router.post("/")
async def create_conversation(user: dict = Depends(get_current_user), title: Optional[str] = "Nueva conversación"):
    """Crea una nueva conversación para el usuario actual"""
    try:
        # Sanitizar y limitar título
        safe_title = re.sub(r'<[^>]+>', '', (title or "Nueva conversación")[:200]).strip()
        if not safe_title:
            safe_title = "Nueva conversación"

        client = supabase_service.get_client()
        result = client.table("conversations") \
            .insert({"title": safe_title, "username": user["username"]}) \
            .execute()

        return {"success": True, "conversation": result.data[0]}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error interno")


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str, user: dict = Depends(get_current_user)):
    """Obtiene una conversación con sus mensajes (solo si pertenece al usuario)"""
    _validate_uuid(conversation_id)
    try:
        client = supabase_service.get_client()

        def _fetch_conversation():
            # Obtener conversación verificando ownership
            return client.table("conversations") \
                .select("*") \
                .eq("id", conversation_id) \
                .eq("username", user["username"]) \
                .single() \
                .execute()

        def _fetch_messages():
            return client.table("messages") \
                .select("*") \
                .eq("conversation_id", conversation_id) \
                .order("created_at") \
                .execute()

        # Ambas consultas son independientes entre sí: se piden en paralelo
        # (si la conversación no pertenece al usuario, los mensajes se descartan más abajo)
        conv, msgs = await asyncio.gather(
            asyncio.to_thread(_fetch_conversation),
            asyncio.to_thread(_fetch_messages),
        )

        if not conv.data:
            raise HTTPException(status_code=404, detail="Conversación no encontrada")

        return {
            "success": True,
            "conversation": conv.data,
            "messages": msgs.data
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error interno")


@router.post("/{conversation_id}/messages")
async def add_message(conversation_id: str, message: MessageCreate, user: dict = Depends(get_current_user)):
    """Agrega un mensaje a la conversación (solo si pertenece al usuario)"""
    _validate_uuid(conversation_id)
    try:
        client = supabase_service.get_client()

        # Verificar que la conversación pertenece al usuario
        conv = client.table("conversations") \
            .select("id") \
            .eq("id", conversation_id) \
            .eq("username", user["username"]) \
            .execute()
        if not conv.data:
            raise HTTPException(status_code=403, detail="No tenés acceso a esta conversación")

        # Insertar mensaje
        result = client.table("messages") \
            .insert({
                "conversation_id": conversation_id,
                "role": message.role,
                "content": message.safe_content,
                "sources": message.sources
            }) \
            .execute()

        # Actualizar título si es el primer mensaje del usuario
        if message.role == "user":
            msgs = client.table("messages") \
                .select("id") \
                .eq("conversation_id", conversation_id) \
                .eq("role", "user") \
                .limit(2) \
                .execute()

            if len(msgs.data) == 1:  # Es el primer mensaje
                title = re.sub(r'<[^>]+>', '', message.content[:50])
                title = title + ("..." if len(message.content) > 50 else "")
                client.table("conversations") \
                    .update({"title": title, "updated_at": datetime.now(timezone.utc).isoformat()}) \
                    .eq("id", conversation_id) \
                    .execute()
            else:
                client.table("conversations") \
                    .update({"updated_at": datetime.now(timezone.utc).isoformat()}) \
                    .eq("id", conversation_id) \
                    .execute()

        return {"success": True, "message": result.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error interno")


@router.patch("/{conversation_id}")
async def rename_conversation(conversation_id: str, body: dict, user: dict = Depends(get_current_user)):
    """Renombra una conversación (solo si pertenece al usuario)"""
    _validate_uuid(conversation_id)
    title = body.get("title", "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="El título no puede estar vacío")
    safe_title = re.sub(r'<[^>]+>', '', title[:100]).strip()
    if not safe_title:
        raise HTTPException(status_code=400, detail="Título inválido")
    try:
        client = supabase_service.get_client()
        result = client.table("conversations") \
            .update({"title": safe_title}) \
            .eq("id", conversation_id) \
            .eq("username", user["username"]) \
            .execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Conversación no encontrada")
        return {"success": True, "title": safe_title}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Error interno")


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: str, user: dict = Depends(get_current_user)):
    """Elimina una conversación (solo si pertenece al usuario)"""
    _validate_uuid(conversation_id)
    try:
        client = supabase_service.get_client()
        client.table("conversations") \
            .delete() \
            .eq("id", conversation_id) \
            .eq("username", user["username"]) \
            .execute()

        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error interno")
