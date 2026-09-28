"""
Servicio de encriptación para proteger el contenido de los documentos.
Usa Fernet (AES-128-CBC) si está disponible, sino deshabilita encriptación.
"""
import os
import base64
import hashlib
from pathlib import Path
from dotenv import load_dotenv
import logging

# Cargar .env al inicio
load_dotenv(Path(__file__).parent.parent.parent / ".env")

logger = logging.getLogger(__name__)

# Intentar importar cryptography (opcional)
try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("cryptography no disponible - encriptación deshabilitada")


class EncryptionService:
    """
    Servicio para encriptar y desencriptar contenido de documentos.
    """

    def __init__(self):
        self._fernet = None

    def _get_fernet(self):
        """Obtiene o crea la instancia de Fernet"""
        if not CRYPTO_AVAILABLE:
            return None

        if self._fernet is None:
            encryption_key = os.getenv("ENCRYPTION_KEY")

            if not encryption_key:
                return None

            key_bytes = hashlib.sha256(encryption_key.encode()).digest()
            fernet_key = base64.urlsafe_b64encode(key_bytes)
            self._fernet = Fernet(fernet_key)

        return self._fernet

    def is_enabled(self) -> bool:
        """Verifica si la encriptación está habilitada"""
        return CRYPTO_AVAILABLE and os.getenv("ENCRYPTION_KEY") is not None

    def encrypt(self, text: str) -> str:
        """Encripta un texto si es posible, sino retorna el original"""
        if not text:
            return text

        fernet = self._get_fernet()
        if fernet is None:
            return text

        try:
            encrypted = fernet.encrypt(text.encode('utf-8'))
            return "ENC:" + encrypted.decode('utf-8')
        except Exception as e:
            logger.error(f"Error encriptando: {e}")
            return text

    def decrypt(self, text: str) -> str:
        """Desencripta un texto si es posible"""
        if not text:
            return text

        if not text.startswith("ENC:"):
            return text

        fernet = self._get_fernet()
        if fernet is None:
            return text  # Retornar como está si no hay crypto

        try:
            encrypted_data = text[4:]
            decrypted = fernet.decrypt(encrypted_data.encode('utf-8'))
            return decrypted.decode('utf-8')
        except Exception as e:
            logger.error(f"Error desencriptando: {e}")
            return text


encryption_service = EncryptionService()
