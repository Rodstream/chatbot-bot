"""
API de autenticación con cookies firmadas y soporte multi-usuario
"""
from fastapi import APIRouter, Response, Request, Cookie, HTTPException, Depends
from pydantic import BaseModel
import os
import hmac
import hashlib
import secrets
import time
import base64
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Auth"])

# --- Rate limiting simple para login ---
_login_attempts: dict = {}  # IP -> [timestamps]
MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 300  # 5 minutos
_MAX_RATE_LIMIT_ENTRIES = 10000


def _cleanup_rate_limit():
    """Limpia entries viejas si el dict crece demasiado"""
    if len(_login_attempts) > _MAX_RATE_LIMIT_ENTRIES:
        now = time.time()
        stale_ips = [ip for ip, ts in _login_attempts.items()
                     if not ts or now - max(ts) > LOGIN_WINDOW_SECONDS]
        for ip in stale_ips:
            del _login_attempts[ip]


# --- Cache de verificación de existencia de usuario (evita ir a Supabase en cada request) ---
_user_verified_cache: dict = {}  # username -> timestamp de última verificación
_USER_VERIFY_TTL_SECONDS = 60
_MAX_USER_VERIFY_CACHE = 10000


def _cleanup_user_verify_cache():
    """Limpia entries vencidas si el dict crece demasiado"""
    if len(_user_verified_cache) > _MAX_USER_VERIFY_CACHE:
        now = time.time()
        stale = [u for u, ts in _user_verified_cache.items() if now - ts > _USER_VERIFY_TTL_SECONDS]
        for u in stale:
            del _user_verified_cache[u]


def _check_rate_limit(client_ip: str) -> bool:
    """Retorna True si el IP está dentro del límite, False si excedió"""
    _cleanup_rate_limit()
    now = time.time()
    attempts = _login_attempts.get(client_ip, [])
    # Limpiar intentos viejos
    attempts = [t for t in attempts if now - t < LOGIN_WINDOW_SECONDS]
    _login_attempts[client_ip] = attempts
    return len(attempts) < MAX_LOGIN_ATTEMPTS


def _record_attempt(client_ip: str):
    """Registra un intento de login"""
    if client_ip not in _login_attempts:
        _login_attempts[client_ip] = []
    _login_attempts[client_ip].append(time.time())


class LoginRequest(BaseModel):
    username: str
    password: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "user"


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# --- Password hashing (stdlib, sin dependencias externas) ---

def hash_password(password: str) -> str:
    """Hash password con PBKDF2-SHA256 y salt aleatorio"""
    salt = secrets.token_hex(16)
    pw_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        iterations=260000
    ).hex()
    return f"{salt}${pw_hash}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verifica password contra el hash almacenado"""
    try:
        salt, pw_hash = stored_hash.split('$', 1)
        new_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            iterations=260000
        ).hex()
        return secrets.compare_digest(new_hash, pw_hash)
    except Exception:
        return False


# --- Token management ---

def get_secret():
    """Obtiene la clave secreta para firmar cookies"""
    from app.core.config import settings
    return settings.SESSION_SECRET


# Hash de fallback para desarrollo si no se configuró ADMIN_PASSWORD_HASH.
# Corresponde a la password "admin123"; en producción el arranque falla si se usa este fallback.
_DEFAULT_ADMIN_PASSWORD_HASH = hash_password("admin123")


def get_admin_credentials():
    """Obtiene las credenciales de admin desde las variables de entorno.
    El password se almacena como hash PBKDF2, nunca en texto plano."""
    return {
        "username": os.getenv("ADMIN_USERNAME", "admin"),
        "password_hash": os.getenv("ADMIN_PASSWORD_HASH") or _DEFAULT_ADMIN_PASSWORD_HASH
    }


def create_signed_token(username: str, role: str) -> str:
    """Crea un token firmado con HMAC incluyendo rol"""
    timestamp = str(int(time.time()))
    data = f"{username}|{role}|{timestamp}"
    signature = hmac.new(
        get_secret().encode(),
        data.encode(),
        hashlib.sha256
    ).hexdigest()
    token = base64.urlsafe_b64encode(f"{data}|{signature}".encode()).decode()
    return token


def verify_signed_token(token: Optional[str]) -> Optional[dict]:
    """Verifica un token firmado y retorna {username, role} si es válido"""
    if not token:
        return None

    try:
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        # Separar en exactamente 4 partes: username|role|timestamp|signature
        # La firma es de 64 chars, así que tomamos los últimos 64 como firma
        last_pipe = decoded.rfind("|")
        if last_pipe == -1:
            return None
        signature = decoded[last_pipe + 1:]
        remaining = decoded[:last_pipe]
        parts = remaining.split("|")
        if len(parts) != 3:
            return None

        username, role, timestamp = parts

        # Verificar que no haya expirado (7 días)
        token_time = int(timestamp)
        if time.time() - token_time > 86400 * 7:
            return None

        # Verificar firma completa (64 chars SHA256)
        data = f"{username}|{role}|{timestamp}"
        expected_signature = hmac.new(
            get_secret().encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()

        if hmac.compare_digest(signature, expected_signature):
            return {"username": username, "role": role}

    except Exception:
        pass

    return None


def is_authenticated(session_token: Optional[str]) -> Optional[dict]:
    """Verifica si el usuario está autenticado. Retorna dict o None."""
    return verify_signed_token(session_token)


# --- FastAPI dependencies ---

async def get_current_user(session_token: Optional[str] = Cookie(None)) -> dict:
    """Dependencia FastAPI: retorna usuario o 401. Valida que el usuario aún exista en DB
    (con cache corto para no golpear Supabase en cada request)."""
    user = verify_signed_token(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="No autenticado")

    # El superadmin viene de env vars, no necesita fila en DB
    superadmin = get_admin_credentials()
    if user["username"] != superadmin["username"]:
        now = time.time()
        last_verified = _user_verified_cache.get(user["username"])
        if last_verified is not None and now - last_verified < _USER_VERIFY_TTL_SECONDS:
            return user
        try:
            _cleanup_user_verify_cache()
            client = _get_supabase_client()
            res = client.table("users").select("username").eq("username", user["username"]).execute()
            if not res.data:
                raise HTTPException(status_code=401, detail="Usuario eliminado o no encontrado")
            _user_verified_cache[user["username"]] = now
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"No se pudo verificar existencia del usuario '{user['username']}': {e}")

    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Dependencia FastAPI: requiere rol admin o 403"""
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Se requiere rol admin")
    return user


# --- Supabase client helper ---

def _get_supabase_client():
    from app.services.supabase_service import supabase_service
    return supabase_service.get_client()


# --- Endpoints ---

@router.post("/login")
async def login(request: LoginRequest, response: Response, req: Request = None):
    """Login: primero chequea superadmin, luego tabla users"""
    # Rate limiting
    client_ip = req.client.host if req and req.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Demasiados intentos. Esperá 5 minutos."
        )

    credentials = get_admin_credentials()

    # 1. Chequear superadmin (env vars)
    if secrets.compare_digest(request.username, credentials["username"]) and verify_password(request.password, credentials["password_hash"]):
        token = create_signed_token(request.username, "admin")
        response.set_cookie(
            key="session_token", value=token,
            httponly=True, max_age=86400 * 7, samesite="lax", secure=os.getenv("ENVIRONMENT", "development") != "development"
        )
        return {"success": True, "message": "Login exitoso"}

    # 2. Chequear tabla users en Supabase
    try:
        client = _get_supabase_client()
        result = client.table("users").select("*").eq("username", request.username).execute()
        if result.data and len(result.data) == 1:
            user = result.data[0]
            if verify_password(request.password, user["password_hash"]):
                token = create_signed_token(user["username"], user["role"])
                response.set_cookie(
                    key="session_token", value=token,
                    httponly=True, max_age=86400 * 7, samesite="lax", secure=os.getenv("ENVIRONMENT", "development") != "development"
                )
                return {"success": True, "message": "Login exitoso"}
    except Exception as e:
        logger.error(f"Error consultando users: {e}")

    _record_attempt(client_ip)
    logger.warning(f"Login fallido para usuario '{request.username}' desde {client_ip}")
    raise HTTPException(status_code=401, detail="Credenciales inválidas")


@router.post("/logout")
async def logout(response: Response):
    """Endpoint de logout"""
    response.delete_cookie("session_token")
    return {"success": True, "message": "Logout exitoso"}


@router.get("/check")
async def check_auth(session_token: Optional[str] = Cookie(None)):
    """Verifica autenticación y retorna username + role + display_name"""
    user = verify_signed_token(session_token)
    if user:
        superadmin = get_admin_credentials()
        display_name = None
        try:
            client = _get_supabase_client()
            res = client.table("users").select("display_name").eq("username", user["username"]).execute()
            if res.data:
                display_name = res.data[0].get("display_name")
            elif user["username"] != superadmin["username"]:
                # Usuario no encontrado en DB y no es superadmin → sesión inválida
                return {"authenticated": False}
        except Exception:
            pass
        return {"authenticated": True, "username": user["username"], "role": user["role"], "display_name": display_name}
    return {"authenticated": False}


class UpdateDisplayNameRequest(BaseModel):
    display_name: str

@router.patch("/display-name")
async def update_display_name(request: UpdateDisplayNameRequest, user: dict = Depends(get_current_user)):
    """Actualiza el nombre para mostrar del usuario"""
    name = request.display_name.strip()
    if not name or len(name) > 60:
        raise HTTPException(status_code=400, detail="El nombre debe tener entre 1 y 60 caracteres")
    import json
    try:
        client = _get_supabase_client()
        res = client.table("users").select("id").eq("username", user["username"]).execute()
        if not res.data:
            # Superadmin sin fila: crearla
            client.table("users").insert({
                "username": user["username"], "password_hash": "__superadmin__",
                "role": user["role"], "created_by": "system", "display_name": name
            }).execute()
        else:
            client.table("users").update({"display_name": name}).eq("username", user["username"]).execute()
        return {"success": True, "display_name": name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- User CRUD (solo admin) ---

@router.get("/users")
async def list_users(admin: dict = Depends(require_admin)):
    """Lista todos los usuarios"""
    client = _get_supabase_client()
    result = client.table("users").select("id, username, role, created_at, created_by").execute()

    superadmin = get_admin_credentials()
    superadmin_entry = {"username": superadmin["username"], "role": "admin", "is_superadmin": True}
    # Exclude any DB row with the same username as the superadmin (auto-created for preferences)
    db_users = [u for u in (result.data or []) if u["username"] != superadmin["username"]]
    return {"success": True, "users": [superadmin_entry] + db_users}


@router.post("/users")
async def create_user(request: CreateUserRequest, admin: dict = Depends(require_admin)):
    """Crear un nuevo usuario (solo admin)"""
    import re as _re
    if not request.username or len(request.username) < 3 or len(request.username) > 50:
        raise HTTPException(status_code=400, detail="Username debe tener entre 3 y 50 caracteres")
    if not _re.match(r'^[a-zA-Z0-9_.-]+$', request.username):
        raise HTTPException(status_code=400, detail="Username solo puede contener letras, números, guiones y puntos")
    if not request.password or len(request.password) < 6 or len(request.password) > 128:
        raise HTTPException(status_code=400, detail="Password debe tener entre 6 y 128 caracteres")
    if request.role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="Rol inválido. Usar 'admin' o 'user'")

    superadmin = get_admin_credentials()
    if request.username == superadmin["username"]:
        raise HTTPException(status_code=400, detail="Nombre de usuario reservado")

    pw_hash = hash_password(request.password)
    client = _get_supabase_client()

    try:
        client.table("users").insert({
            "username": request.username,
            "password_hash": pw_hash,
            "role": request.role,
            "created_by": admin["username"]
        }).execute()
        return {"success": True, "user": {"username": request.username, "role": request.role}}
    except Exception as e:
        logger.error(f"Create user error: {e}")
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
            raise HTTPException(status_code=400, detail="El usuario ya existe")
        raise HTTPException(status_code=500, detail="Error al crear usuario")


@router.post("/change-password")
async def change_password(request: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    """Permite al usuario cambiar su propia contraseña"""
    if len(request.new_password) < 6 or len(request.new_password) > 128:
        raise HTTPException(status_code=400, detail="La nueva contraseña debe tener entre 6 y 128 caracteres")

    # El superadmin no tiene registro en la tabla users
    superadmin = get_admin_credentials()
    if user["username"] == superadmin["username"]:
        raise HTTPException(status_code=400, detail="El superadmin no puede cambiar su contraseña desde aquí")

    client = _get_supabase_client()
    result = client.table("users").select("password_hash").eq("username", user["username"]).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if not verify_password(request.current_password, result.data[0]["password_hash"]):
        raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")

    new_hash = hash_password(request.new_password)
    client.table("users").update({"password_hash": new_hash}).eq("username", user["username"]).execute()
    return {"success": True}


def _parse_favs(raw) -> list:
    import json
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return []


@router.get("/favorites")
async def get_favorites(user: dict = Depends(get_current_user)):
    """Retorna lista de IDs de conversaciones favoritas del usuario"""
    import json
    try:
        client = _get_supabase_client()
        res = client.table("users").select("favorites").eq("username", user["username"]).execute()
        if res.data:
            return {"success": True, "favorites": _parse_favs(res.data[0].get("favorites"))}
    except Exception:
        pass
    return {"success": True, "favorites": []}


class ToggleFavoriteRequest(BaseModel):
    conv_id: str

@router.post("/favorites/toggle")
async def toggle_favorite(request: ToggleFavoriteRequest, user: dict = Depends(get_current_user)):
    """Agrega o quita una conversación de favoritos"""
    import json
    try:
        client = _get_supabase_client()
        res = client.table("users").select("favorites").eq("username", user["username"]).execute()
        if not res.data:
            # El superadmin (env vars) no tiene fila en DB: la creamos automáticamente
            new_favs = [request.conv_id]
            client.table("users").insert({
                "username": user["username"],
                "password_hash": "__superadmin__",
                "role": user["role"],
                "created_by": "system",
                "favorites": json.dumps(new_favs)
            }).execute()
            return {"success": True, "favorites": new_favs}
        favs = _parse_favs(res.data[0].get("favorites"))
        if request.conv_id in favs:
            favs.remove(request.conv_id)
        else:
            favs.append(request.conv_id)
        upd = client.table("users").update({"favorites": json.dumps(favs)}).eq("username", user["username"]).execute()
        if not upd.data:
            raise HTTPException(status_code=500, detail="El UPDATE no afectó ninguna fila. Verificá que la columna 'favorites' exista en la tabla 'users' de Supabase.")
        return {"success": True, "favorites": favs}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al guardar favorito: {str(e)}")


@router.delete("/users/{username}")
async def delete_user(username: str, admin: dict = Depends(require_admin)):
    """Eliminar un usuario (solo admin)"""
    superadmin = get_admin_credentials()
    if username == superadmin["username"]:
        raise HTTPException(status_code=400, detail="No se puede eliminar el superadmin")

    client = _get_supabase_client()
    result = client.table("users").delete().eq("username", username).execute()
    deleted = len(result.data) if result.data else 0

    if deleted == 0:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    _user_verified_cache.pop(username, None)

    return {"success": True}
