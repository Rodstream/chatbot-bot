from fastapi import FastAPI, Cookie, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
load_dotenv()  # Cargar variables de entorno antes de importar otros módulos
from app.core.config import settings
from app.api import chat, database, embeddings, documents, search, conversations, auth, admin, feedback, incidents
import uvicorn
import sys
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# --- Validación de seguridad al arrancar ---
_KNOWN_WEAK_SECRETS = {"default-secret", "default-secret-change-me", ""}
_insecure = []
if settings.SESSION_SECRET in _KNOWN_WEAK_SECRETS or len(settings.SESSION_SECRET) < 32:
    _insecure.append("SESSION_SECRET es demasiado corto o tiene valor por defecto (mínimo 32 caracteres)")
if not settings.ADMIN_PASSWORD_HASH:
    _insecure.append("ADMIN_PASSWORD_HASH no configurado (usando password por defecto admin123)")

if _insecure:
    for msg in _insecure:
        logger.critical(f"SEGURIDAD: {msg}")
    if settings.ENVIRONMENT != "development":
        print("\n*** ERROR: Configuración insegura detectada en producción ***")
        for msg in _insecure:
            print(f"  - {msg}")
        print("Configurá las variables de entorno correctamente antes de arrancar.\n")
        sys.exit(1)
    else:
        print("\n*** ADVERTENCIA: Configuración insegura (solo aceptable en desarrollo local) ***")
        for msg in _insecure:
            print(f"  - {msg}")

# Crear la aplicación FastAPI
_is_dev = settings.ENVIRONMENT == "development"
app = FastAPI(
    title="Raúl - RAG Assistant API",
    description="API para agente conversacional con sistema RAG para BECHA SA",
    version="1.0.0",
    docs_url="/docs" if _is_dev else None,
    redoc_url="/redoc" if _is_dev else None,
)

# Security headers middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https://*.supabase.co blob: https://www.transparenttextures.com; connect-src 'self' https://*.supabase.co https://cdn.jsdelivr.net; frame-src 'self' https://view.officeapps.live.com https://docs.google.com https://*.supabase.co"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=()"
        if settings.ENVIRONMENT != "development":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response

app.add_middleware(SecurityHeadersMiddleware)


# Body size limit middleware (1MB para non-file endpoints)
class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    MAX_BODY_SIZE = 1 * 1024 * 1024  # 1MB

    async def dispatch(self, request: Request, call_next):
        # Excluir uploads que tienen su propio límite
        if request.url.path == "/api/documents/upload" or "/attachments" in request.url.path:
            return await call_next(request)
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.MAX_BODY_SIZE:
            return Response(content="Request body too large", status_code=413)
        return await call_next(request)

app.add_middleware(BodySizeLimitMiddleware)

# Configurar CORS - restringir orígenes
import os
allowed_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
allowed_origins = [o.strip() for o in allowed_origins if o.strip()]
if not allowed_origins:
    allowed_origins = [settings.FRONTEND_URL]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

# Montar archivos estáticos
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Incluir routers
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(database.router)
app.include_router(embeddings.router)
app.include_router(documents.router)
app.include_router(search.router)
app.include_router(conversations.router)
app.include_router(admin.router)
app.include_router(feedback.router)
app.include_router(incidents.router)


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    """
    Página de login
    """
    template_path = Path(__file__).parent / "templates" / "login.html"
    return template_path.read_text(encoding="utf-8")


@app.get("/", response_class=HTMLResponse)
async def root(session_token: Optional[str] = Cookie(None)):
    """
    Sirve la interfaz de usuario (protegida)
    """
    # Verificar autenticación (retorna dict o None)
    if not auth.verify_signed_token(session_token):
        return RedirectResponse(url="/login", status_code=302)

    template_path = Path(__file__).parent / "templates" / "index.html"
    return template_path.read_text(encoding="utf-8")


@app.get("/health")
async def health_check():
    """
    Endpoint de salud - Verifica que el servidor está funcionando
    """
    return {
        "status": "healthy",
        "message": "Raúl está listo para trabajar"
    }


@app.get("/api/test")
async def test_endpoint(admin: dict = Depends(auth.require_admin)):
    """
    Endpoint de prueba - Solo admin
    """
    return {
        "success": True,
        "message": "La API está funcionando correctamente"
    }


# Para ejecutar con: python -m app.main
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=(settings.ENVIRONMENT == "development")
    )
