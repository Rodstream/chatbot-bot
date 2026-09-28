"""Servicio de envío de mails vía Resend (https://resend.com)."""
import base64
import logging

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


class EmailService:
    """Envía mails con adjuntos usando la API de Resend."""

    def is_enabled(self) -> bool:
        return bool(settings.RESEND_API_KEY)

    def send_with_attachment(
        self,
        to: str,
        subject: str,
        html: str,
        attachment_filename: str,
        attachment_bytes: bytes,
    ) -> None:
        """Envía un mail con un archivo adjunto. Lanza una excepción si falla."""
        if not self.is_enabled():
            raise RuntimeError("El envío de mails no está configurado (falta RESEND_API_KEY)")

        payload = {
            "from": settings.RESEND_FROM_EMAIL,
            "to": [to],
            "subject": subject,
            "html": html,
            "attachments": [{
                "filename": attachment_filename,
                "content": base64.b64encode(attachment_bytes).decode("ascii"),
            }],
        }
        resp = requests.post(
            RESEND_API_URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            timeout=20,
        )
        if resp.status_code >= 300:
            logger.error(f"Resend error {resp.status_code}: {resp.text}")
            raise RuntimeError(f"Resend rechazó el envío ({resp.status_code})")


email_service = EmailService()
