"""
API de documentos con permisos por rol
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from typing import Optional
from datetime import datetime
import tempfile
import os
import json
import subprocess
import sys
import logging
from pathlib import Path

from app.services.supabase_service import supabase_service
from app.api.auth import require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["Documents"])


ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.xlsx', '.txt'}


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    document_type: Optional[str] = Form("documento"),
    obra: Optional[str] = Form(None),
    fecha: Optional[str] = Form(None),
    user: dict = Depends(require_admin)
):
    """Sube y procesa un documento (PDF, Word, Excel, TXT). Solo admin."""

    # Sanitizar filename - solo el nombre, sin path traversal
    safe_filename = Path(file.filename).name
    if not safe_filename or safe_filename.startswith('.'):
        raise HTTPException(status_code=400, detail="Nombre de archivo inválido")

    ext = Path(safe_filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no soportado. Formatos aceptados: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    tmp_path = None

    try:
        # Guardar archivo temp (streaming) con límite de 50MB
        max_size = 50 * 1024 * 1024  # 50MB
        total_size = 0
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            while chunk := await file.read(8192):
                total_size += len(chunk)
                if total_size > max_size:
                    tmp_path = tmp.name
                    raise HTTPException(status_code=413, detail="Archivo demasiado grande (máximo 50MB)")
                tmp.write(chunk)
            tmp_path = tmp.name

        # Preparar fecha
        fecha_iso = ""
        if fecha:
            try:
                fecha_iso = datetime.fromisoformat(fecha).isoformat()
            except:
                pass

        # Ejecutar worker en proceso separado
        worker = Path(__file__).parent.parent / "services" / "ingest_worker.py"

        proc = subprocess.run(
            [sys.executable, str(worker), tmp_path, safe_filename,
             document_type or "documento", obra or "", fecha_iso,
             user["username"]],
            capture_output=True,
            text=True,
            timeout=180
        )

        # Limpiar temp
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

        # Procesar resultado
        if proc.returncode != 0:
            logger.error(f"Worker error: {proc.stderr[:500] if proc.stderr else 'unknown'}")
            raise HTTPException(status_code=500, detail="Error al procesar el documento")

        result = json.loads(proc.stdout)

        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Error"))

        return {**result, "filename": safe_filename}

    except subprocess.TimeoutExpired:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise HTTPException(status_code=500, detail="Timeout procesando documento")

    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Error interno")

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Upload error: {e}")
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise HTTPException(status_code=500, detail="Error al subir el documento")


@router.get("/sources")
async def list_sources(user: dict = Depends(require_admin)):
    """Lista documentos cargados con info de quién los subió. Solo admin."""
    try:
        client = supabase_service.get_client()
        result = client.table("documents").select("source, uploaded_by, document_type, obra, fecha, created_at").execute()

        # Deduplicar por source, conservando metadata del primer chunk
        sources_map = {}
        for d in result.data:
            src = d.get("source")
            if src and src not in sources_map:
                sources_map[src] = {
                    "uploaded_by": d.get("uploaded_by"),
                    "document_type": d.get("document_type"),
                    "obra": d.get("obra"),
                    "fecha": d.get("fecha"),
                    "created_at": d.get("created_at"),
                }

        sources = [{"source": s, **meta} for s, meta in sources_map.items()]
        return {"success": True, "sources": sources, "count": len(sources)}
    except Exception as e:
        logger.error(f"List sources error: {e}")
        raise HTTPException(status_code=500, detail="Error al listar documentos")


@router.get("/filters")
async def get_filters(user: dict = Depends(require_admin)):
    """Retorna valores únicos de document_type y obra para filtros. Solo admin."""
    try:
        client = supabase_service.get_client()
        result = client.table("documents").select("document_type, obra").execute()

        types = sorted(set(d["document_type"] for d in result.data if d.get("document_type")))
        obras = sorted(set(d["obra"] for d in result.data if d.get("obra")))

        return {"success": True, "document_types": types, "obras": obras}
    except Exception as e:
        logger.error(f"Filters error: {e}")
        return {"success": True, "document_types": [], "obras": []}


@router.delete("/by-source/{source_name}")
async def delete_by_source(source_name: str, user: dict = Depends(require_admin)):
    """Elimina un documento (solo admin)."""
    import re as _re
    if not source_name or len(source_name) > 255 or not _re.match(r'^[\w\-. ]+$', source_name):
        raise HTTPException(status_code=400, detail="Nombre de documento inválido")
    try:
        client = supabase_service.get_client()
        result = client.table("documents").delete().eq("source", source_name).execute()
        deleted = len(result.data) if result.data else 0
        return {"success": True, "deleted": deleted}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete error: {e}")
        raise HTTPException(status_code=500, detail="Error al eliminar documento")


@router.delete("/all")
async def delete_all(admin: dict = Depends(require_admin)):
    """Elimina todos los documentos (solo admin)"""
    try:
        client = supabase_service.get_client()
        result = client.table("documents").delete().neq("id", 0).execute()
        return {"success": True, "deleted": len(result.data) if result.data else 0}
    except Exception as e:
        logger.error(f"Delete all error: {e}")
        raise HTTPException(status_code=500, detail="Error al eliminar documentos")
