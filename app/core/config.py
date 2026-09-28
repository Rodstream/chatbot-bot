from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """
    Configuración general de la aplicación.
    Lee las variables de entorno desde el archivo .env
    """

    # Server
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    ENVIRONMENT: str = "development"

    # API Keys
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None

    # Supabase
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None

    # Encryption (opcional - si no se configura, el contenido no se encripta)
    ENCRYPTION_KEY: Optional[str] = None

    # Resend (envío de mails vía API HTTPS). Sin RESEND_API_KEY, el envío queda deshabilitado.
    RESEND_API_KEY: Optional[str] = None
    RESEND_FROM_EMAIL: str = "Raúl (BECHA SA) <agenteia@bechadrive.com>"

    # Google Drive (respaldo de reportes). Sin ambas variables, el respaldo queda deshabilitado.
    GOOGLE_SERVICE_ACCOUNT_JSON: Optional[str] = None
    GOOGLE_DRIVE_FOLDER_ID: Optional[str] = None

    # Frontend
    FRONTEND_URL: str = "http://localhost:5173"

    # Auth
    ADMIN_USERNAME: str = "admin"
    # Hash PBKDF2 (formato salt$hash, generado con hash_password()). Nunca texto plano.
    ADMIN_PASSWORD_HASH: Optional[str] = None
    SESSION_SECRET: str = "default-secret"

    # Usage limits (0 = unlimited)
    DAILY_MESSAGE_LIMIT: int = 0

    # Response cache (0 = disabled)
    CACHE_TTL_SECONDS: int = 3600
    CACHE_MAX_ENTRIES: int = 500

    class Config:
        env_file = ".env"
        case_sensitive = True


# Instancia global de configuración
settings = Settings()
