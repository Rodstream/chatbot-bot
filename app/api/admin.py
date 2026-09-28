"""API de administración - dashboard, estadísticas y logs"""
from fastapi import APIRouter, Depends, HTTPException
from app.services.supabase_service import supabase_service
from app.services.search_service import cache_clear, cache_stats
from app.api.auth import require_admin
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.get("/stats")
async def get_stats(admin: dict = Depends(require_admin)):
    """Estadísticas del sistema (solo admin)"""
    try:
        client = supabase_service.get_client()

        # Total documents (unique sources)
        docs_result = client.table("documents").select("source").execute()
        unique_sources = set(d.get("source") for d in docs_result.data if d.get("source"))
        total_chunks = len(docs_result.data)

        # Total conversations
        convs_result = client.table("conversations").select("id, username").execute()
        total_conversations = len(convs_result.data)
        users_with_convs = set(c.get("username") for c in convs_result.data if c.get("username"))

        # Total messages
        msgs_result = client.table("messages").select("id, role").execute()
        total_messages = len(msgs_result.data)
        user_messages = sum(1 for m in msgs_result.data if m.get("role") == "user")
        assistant_messages = sum(1 for m in msgs_result.data if m.get("role") == "assistant")

        # Users from auth table
        users_result = client.table("users").select("id, role").execute()
        total_users = len(users_result.data)
        admin_users = sum(1 for u in users_result.data if u.get("role") == "admin")

        return {
            "success": True,
            "stats": {
                "documents": len(unique_sources),
                "chunks": total_chunks,
                "conversations": total_conversations,
                "messages": total_messages,
                "user_messages": user_messages,
                "assistant_messages": assistant_messages,
                "users": total_users,
                "admin_users": admin_users,
                "active_users": len(users_with_convs),
                "cache": cache_stats(),
            }
        }
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return {"success": False, "stats": {}}


@router.post("/cache/clear")
async def clear_cache(admin: dict = Depends(require_admin)):
    """Limpia el cache de respuestas (solo admin)"""
    cache_clear()
    return {"success": True, "message": "Cache limpiado"}


@router.get("/conversations")
async def list_all_conversations(admin: dict = Depends(require_admin)):
    """Lista todas las conversaciones de todos los usuarios (solo admin)"""
    try:
        client = supabase_service.get_client()
        result = client.table("conversations") \
            .select("id, title, username, created_at, updated_at") \
            .order("updated_at", desc=True) \
            .limit(100) \
            .execute()

        return {"success": True, "conversations": result.data or []}
    except Exception as e:
        logger.error(f"Admin conversations error: {e}")
        return {"success": False, "conversations": []}


@router.get("/conversations/{conversation_id}")
async def get_conversation_messages(conversation_id: str, admin: dict = Depends(require_admin)):
    """Ver los mensajes de una conversación (solo admin)"""
    import uuid as _uuid
    try:
        _uuid.UUID(conversation_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="ID inválido")

    try:
        client = supabase_service.get_client()

        conv = client.table("conversations") \
            .select("id, title, username, created_at") \
            .eq("id", conversation_id) \
            .execute()

        if not conv.data:
            raise HTTPException(status_code=404, detail="Conversación no encontrada")

        msgs = client.table("messages") \
            .select("role, content, created_at") \
            .eq("conversation_id", conversation_id) \
            .order("created_at") \
            .execute()

        return {
            "success": True,
            "conversation": conv.data[0],
            "messages": msgs.data or []
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin conversation detail error: {e}")
        raise HTTPException(status_code=500, detail="Error interno")


@router.delete("/conversations/{conversation_id}")
async def delete_conversation_admin(conversation_id: str, admin: dict = Depends(require_admin)):
    """Elimina una conversación y sus mensajes (solo admin)"""
    import uuid as _uuid
    try:
        _uuid.UUID(conversation_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="ID inválido")

    try:
        client = supabase_service.get_client()
        client.table("messages").delete().eq("conversation_id", conversation_id).execute()
        result = client.table("conversations").delete().eq("id", conversation_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Conversación no encontrada")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin delete conversation error: {e}")
        raise HTTPException(status_code=500, detail="Error interno")
