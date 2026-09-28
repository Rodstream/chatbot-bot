"""API para reportes de incidentes en obra"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List
from datetime import datetime
import uuid as _uuid
import logging
import re as _re
from pathlib import Path

from app.services.supabase_service import supabase_service
from app.services.embeddings_service import embeddings_service
from app.services.email_service import email_service
from app.services.drive_service import drive_service
from app.api.auth import get_current_user, require_admin

BUCKET = "incident-files"
ALLOWED_ATTACHMENT_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.pdf', '.docx', '.xlsx', '.txt'}
MAX_ATTACHMENT_SIZE = 20 * 1024 * 1024  # 20MB

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/incidents", tags=["Incidents"])


class IncidentReport(BaseModel):
    fecha: str = ""
    n_obra: str = ""
    provincia: str = ""
    unidad_productiva: str = ""
    operador_referente: str = ""
    jefe_equipo: str = ""
    tipo_registro: List[str] = []
    area_involucrada: List[str] = []
    area_otro: str = ""
    descripcion: str = ""
    como_se_resolvio: str = ""
    impacto_operativo: str = ""
    aplicabilidad: str = ""
    requiere_analisis: str = ""
    responsable_nombre: str = ""
    responsable_area: str = ""
    responsable_email: str = ""
    resultado_final: List[str] = []
    observaciones_finales: str = ""
    documentacion_asociada: List[str] = []
    registro_por: str = ""
    registro_area: str = ""


def _report_to_text(d: dict) -> str:
    """Convierte los campos del reporte a texto plano para RAG."""
    parts = [
        "REGISTRO DE INCIDENTE EN OBRA",
        f"Fecha: {d.get('fecha', '')}",
        f"N° de Obra: {d.get('n_obra', '')}",
        f"Provincia: {d.get('provincia', '')}",
        f"Unidad Productiva: {d.get('unidad_productiva', '')}",
        f"Gestor a cargo de la obra: {d.get('operador_referente', '')}",
        f"Jefe de equipo: {d.get('jefe_equipo', '')}",
        f"Tipo de registro: {', '.join(d.get('tipo_registro', []))}",
        f"Área involucrada: {', '.join(d.get('area_involucrada', []))}",
    ]
    if d.get("area_otro"):
        parts.append(f"Área otro: {d['area_otro']}")
    parts += [
        f"Descripción: {d.get('descripcion', '')}",
        f"Cómo se resolvió: {d.get('como_se_resolvio', '')}",
        f"Impacto operativo: {d.get('impacto_operativo', '')}",
        f"Aplicabilidad: {d.get('aplicabilidad', '')}",
        f"Requiere análisis técnico/calidad: {d.get('requiere_analisis', '')}",
        f"Responsable de seguimiento - Nombre: {d.get('responsable_nombre', '')}",
        f"Responsable de seguimiento - Área: {d.get('responsable_area', '')}",
        f"Responsable de seguimiento - Email: {d.get('responsable_email', '')}",
        f"Resultado final: {', '.join(d.get('resultado_final', []))}",
        f"Observaciones finales: {d.get('observaciones_finales', '')}",
        f"Documentación asociada: {', '.join(d.get('documentacion_asociada', []))}",
        f"Registro realizado por: {d.get('registro_por', '')}",
        f"Área de registro: {d.get('registro_area', '')}",
    ]
    return "\n".join(p for p in parts if p.split(": ", 1)[-1].strip())


def _generate_numero_registro(client) -> str:
    """Genera un número de registro secuencial legible, ej: INC-2026-0001"""
    prefix = f"INC-{datetime.now().year}-"
    try:
        result = (
            client.table("incident_reports")
            .select("numero_registro")
            .like("numero_registro", f"{prefix}%")
            .order("numero_registro", desc=True)
            .limit(1)
            .execute()
        )
        last_num = int(result.data[0]["numero_registro"].rsplit("-", 1)[-1]) if result.data else 0
    except Exception:
        last_num = 0
    return f"{prefix}{last_num + 1:04d}"


def _get_numero_registro(client, incident_id: str) -> str:
    """Obtiene el número de registro de un reporte, o el ID si no se encuentra."""
    try:
        res = client.table("incident_reports").select("numero_registro").eq("id", incident_id).execute()
        if res.data and res.data[0].get("numero_registro"):
            return res.data[0]["numero_registro"]
    except Exception:
        pass
    return incident_id


@router.post("/")
async def create_incident(report: IncidentReport, user: dict = Depends(get_current_user)):
    """Crea un reporte de incidente y lo indexa en RAG (cualquier usuario autenticado)."""
    client = supabase_service.get_client()
    report_id = str(_uuid.uuid4())
    doc_source = f"incidente_{report_id}"
    numero_registro = _generate_numero_registro(client)

    try:
        client.table("incident_reports").insert({
            "id": report_id,
            "numero_registro": numero_registro,
            "data": report.dict(),
            "created_by": user["username"],
            "doc_source": doc_source,
        }).execute()

        text = f"N° de Registro: {numero_registro}\n" + _report_to_text(report.dict())
        embedding = embeddings_service.generate_embedding(text)
        client.table("documents").insert({
            "content": text,
            "embedding": embedding,
            "source": doc_source,
            "page_number": 1,
            "document_type": "incidente",
            "obra": report.n_obra or None,
            "fecha": report.fecha or None,
            "uploaded_by": user["username"],
            "metadata": {"incident_id": report_id, "numero_registro": numero_registro},
        }).execute()

        return {"success": True, "id": report_id, "numero_registro": numero_registro}

    except Exception as e:
        logger.error(f"Create incident error: {e}")
        try:
            client.table("incident_reports").delete().eq("id", report_id).execute()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Error al guardar el reporte")


@router.get("/")
async def list_incidents(user: dict = Depends(require_admin)):
    """Lista todos los reportes de incidentes (admin)."""
    try:
        client = supabase_service.get_client()
        result = (
            client.table("incident_reports")
            .select("id, numero_registro, data, created_by, created_at")
            .order("created_at", desc=True)
            .execute()
        )
        return {"success": True, "incidents": result.data}
    except Exception as e:
        logger.error(f"List incidents error: {e}")
        raise HTTPException(status_code=500, detail="Error al listar reportes")


@router.post("/{incident_id}/send-email")
async def send_incident_email(
    incident_id: str,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """Envía el PDF del reporte por mail al responsable de seguimiento (propietario o admin)."""
    try:
        _uuid.UUID(incident_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="ID inválido")

    if not email_service.is_enabled():
        raise HTTPException(status_code=503, detail="El envío de mails no está configurado todavía")

    client = supabase_service.get_client()
    _check_attachment_permission(client, incident_id, user)
    res = client.table("incident_reports").select("data, numero_registro").eq("id", incident_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")

    report = res.data[0]
    d = report.get("data") or {}
    email = (d.get("responsable_email") or "").strip()
    if not email:
        raise HTTPException(status_code=400, detail="El reporte no tiene un email de responsable cargado")

    numero = report.get("numero_registro") or incident_id
    pdf_bytes = await file.read()
    if len(pdf_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="El PDF es demasiado grande para enviar por mail")

    html = (
        f"<p>Hola,</p>"
        f"<p>El reporte <strong>{numero}</strong> requiere de su seguimiento.</p>"
        f"<p>Se adjunta el PDF con el detalle completo.</p>"
        f"<p>— Raúl, asistente BECHA SA</p>"
    )

    try:
        email_service.send_with_attachment(
            to=email,
            subject=f"Reporte {numero} requiere tu seguimiento",
            html=html,
            attachment_filename=f"{numero}.pdf",
            attachment_bytes=pdf_bytes,
        )
    except Exception as e:
        logger.error(f"Send incident email error: {e}")
        raise HTTPException(status_code=502, detail="No se pudo enviar el mail")

    return {"success": True}


@router.delete("/{incident_id}")
async def delete_incident(incident_id: str, admin: dict = Depends(require_admin)):
    """Elimina un reporte, sus adjuntos y su entrada en RAG (solo admin)."""
    try:
        _uuid.UUID(incident_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="ID inválido")

    try:
        client = supabase_service.get_client()
        doc_source = f"incidente_{incident_id}"
        try:
            files = client.storage.from_(BUCKET).list(incident_id)
            if files:
                paths = [f"{incident_id}/{f['name']}" for f in files]
                client.storage.from_(BUCKET).remove(paths)
        except Exception:
            pass
        client.table("incident_reports").delete().eq("id", incident_id).execute()
        client.table("documents").delete().eq("source", doc_source).execute()
        return {"success": True}
    except Exception as e:
        logger.error(f"Delete incident error: {e}")
        raise HTTPException(status_code=500, detail="Error al eliminar reporte")


# ── Adjuntos ────────────────────────────────────────────────────────────────

def _check_attachment_permission(client, incident_id: str, user: dict):
    """Verifica que el usuario puede gestionar adjuntos del reporte.
    Admin: puede en cualquier reporte. User: solo en sus propios reportes."""
    if user["role"] == "admin":
        return
    res = client.table("incident_reports").select("created_by").eq("id", incident_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    if res.data[0]["created_by"] != user["username"]:
        raise HTTPException(status_code=403, detail="Solo podés modificar adjuntos de tus propios reportes")


def _sanitize_filename(name: str) -> str:
    """Reemplaza espacios (incluye variantes unicode como el NNBSP de capturas de Mac)
    y cualquier caracter fuera de [A-Za-z0-9._-], que Supabase Storage rechaza como key."""
    name = _re.sub(r"\s", "_", name)
    return _re.sub(r"[^A-Za-z0-9._-]", "_", name)


@router.post("/{incident_id}/attachments")
async def upload_attachment(
    incident_id: str,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """Sube un archivo adjunto al reporte (propietario o admin)."""
    try:
        _uuid.UUID(incident_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="ID inválido")

    safe_name = _sanitize_filename(Path(file.filename).name)
    if not safe_name or safe_name.startswith('.'):
        raise HTTPException(status_code=400, detail="Nombre de archivo inválido")
    ext = Path(safe_name).suffix.lower()
    if ext not in ALLOWED_ATTACHMENT_EXT:
        raise HTTPException(status_code=400, detail=f"Tipo no permitido. Permitidos: {', '.join(ALLOWED_ATTACHMENT_EXT)}")

    data = await file.read()
    if len(data) > MAX_ATTACHMENT_SIZE:
        raise HTTPException(status_code=413, detail="Archivo demasiado grande (máximo 20MB)")

    storage_path = f"{incident_id}/{safe_name}"
    content_type = file.content_type or "application/octet-stream"

    try:
        client = supabase_service.get_client()
        _check_attachment_permission(client, incident_id, user)

        client.storage.from_(BUCKET).upload(
            path=storage_path,
            file=data,
            file_options={"content-type": content_type, "upsert": "true"},
        )

        if drive_service.is_enabled():
            try:
                numero = _get_numero_registro(client, incident_id)
                drive_service.upload_file(f"{numero}_{safe_name}", data, content_type)
            except Exception as e:
                # El respaldo en Drive es secundario: no debe romper la subida principal.
                logger.warning(f"Drive backup (adjunto) falló para {incident_id}/{safe_name}: {e}")

        return {"success": True, "filename": safe_name}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload attachment error: {e}")
        raise HTTPException(status_code=500, detail="Error al subir el archivo")


@router.post("/{incident_id}/drive-backup")
async def backup_incident_pdf_to_drive(
    incident_id: str,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """Sube una copia del PDF del reporte a Google Drive, si está configurado."""
    try:
        _uuid.UUID(incident_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="ID inválido")

    if not drive_service.is_enabled():
        raise HTTPException(status_code=503, detail="El respaldo en Drive no está configurado todavía")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="El PDF es demasiado grande para respaldar en Drive")

    client = supabase_service.get_client()
    _check_attachment_permission(client, incident_id, user)
    numero = _get_numero_registro(client, incident_id)

    try:
        drive_service.upload_file(f"{numero}.pdf", pdf_bytes, "application/pdf")
    except Exception as e:
        logger.error(f"Drive backup (PDF) error: {e}")
        raise HTTPException(status_code=502, detail="No se pudo subir el PDF a Drive")

    return {"success": True}


@router.get("/{incident_id}/attachments")
async def list_attachments(incident_id: str, user: dict = Depends(require_admin)):
    """Lista los archivos adjuntos de un reporte con URLs firmadas (admin)."""
    try:
        _uuid.UUID(incident_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="ID inválido")

    try:
        client = supabase_service.get_client()
        # También devuelve quién creó el reporte para que el frontend sepa si puede editar
        rep = client.table("incident_reports").select("created_by").eq("id", incident_id).execute()
        report_owner = rep.data[0]["created_by"] if rep.data else ""

        files = client.storage.from_(BUCKET).list(incident_id)
        result = []
        for f in (files or []):
            if isinstance(f, dict):
                name = f.get("name", "")
                meta = f.get("metadata") or {}
                size = meta.get("size") or meta.get("contentLength") or 0
            else:
                name = getattr(f, "name", "")
                size = 0
            if not name:
                continue
            path = f"{incident_id}/{name}"
            try:
                signed = client.storage.from_(BUCKET).create_signed_url(path, 3600)
                if isinstance(signed, dict):
                    url = signed.get("signedURL") or signed.get("signed_url") or signed.get("data", {}).get("signedURL", "")
                else:
                    url = getattr(signed, "signed_url", "") or getattr(signed, "signedURL", "")
            except Exception as e_sign:
                logger.warning(f"create_signed_url failed for {path}: {e_sign}")
                url = ""
            result.append({"name": name, "url": url, "size": size})
        return {"success": True, "attachments": result, "report_owner": report_owner}
    except Exception as e:
        logger.error(f"List attachments error: {e}")
        raise HTTPException(status_code=500, detail=f"Error al listar archivos: {str(e)}")


@router.delete("/{incident_id}/attachments/{filename}")
async def delete_attachment(
    incident_id: str,
    filename: str,
    user: dict = Depends(require_admin),
):
    """Elimina un archivo adjunto (solo admin)."""
    try:
        _uuid.UUID(incident_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="ID inválido")

    import re as _re
    if not filename or not _re.match(r'^[\w\-. ]+$', filename) or len(filename) > 255:
        raise HTTPException(status_code=400, detail="Nombre de archivo inválido")

    try:
        client = supabase_service.get_client()
        _check_attachment_permission(client, incident_id, user)
        client.storage.from_(BUCKET).remove([f"{incident_id}/{filename}"])
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete attachment error: {e}")
        raise HTTPException(status_code=500, detail="Error al eliminar el archivo")
