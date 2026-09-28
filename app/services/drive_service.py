"""Servicio de respaldo de reportes en Google Drive.

Usa una cuenta de servicio de Google (sin interacción humana) para subir copias
de PDFs y adjuntos a una carpeta de Drive compartida con esa cuenta. Deshabilitado
si no están configuradas GOOGLE_SERVICE_ACCOUNT_JSON y GOOGLE_DRIVE_FOLDER_ID.
"""
import json
import logging
from io import BytesIO

from app.core.config import settings

logger = logging.getLogger(__name__)


class DriveService:
    """Sube una copia de PDFs y adjuntos de reportes a una carpeta de Google Drive."""

    def __init__(self):
        self._service = None

    def is_enabled(self) -> bool:
        return bool(settings.GOOGLE_SERVICE_ACCOUNT_JSON and settings.GOOGLE_DRIVE_FOLDER_ID)

    def _get_service(self):
        if self._service is None:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
            credentials = service_account.Credentials.from_service_account_info(
                info, scopes=["https://www.googleapis.com/auth/drive.file"]
            )
            self._service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        return self._service

    def upload_file(self, filename: str, content: bytes, mime_type: str) -> None:
        """Sube un archivo a la carpeta configurada. Lanza excepción si falla."""
        if not self.is_enabled():
            raise RuntimeError("El respaldo en Drive no está configurado")

        from googleapiclient.http import MediaIoBaseUpload

        service = self._get_service()
        media = MediaIoBaseUpload(BytesIO(content), mimetype=mime_type, resumable=False)
        service.files().create(
            body={"name": filename, "parents": [settings.GOOGLE_DRIVE_FOLDER_ID]},
            media_body=media,
            fields="id",
            supportsAllDrives=True,
        ).execute()


drive_service = DriveService()
