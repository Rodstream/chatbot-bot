from fastapi import APIRouter, HTTPException, Depends
from app.services.supabase_service import supabase_service
from app.api.auth import require_admin

router = APIRouter(prefix="/api/database", tags=["Database"])


@router.get("/test-connection")
async def test_connection(admin: dict = Depends(require_admin)):
    """
    Endpoint para verificar que la conexión con Supabase funciona
    """
    try:
        is_connected = await supabase_service.check_connection()

        if is_connected:
            return {
                "success": True,
                "message": "Conexión con Supabase exitosa",
                "database": "PostgreSQL + pgvector en Supabase"
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="No se pudo conectar con Supabase. Verificá tus credenciales."
            )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Error al conectar con la base de datos"
        )


@router.get("/setup")
async def setup_database(admin: dict = Depends(require_admin)):
    """
    Endpoint para verificar el estado de configuración de la base de datos
    """
    try:
        results = await supabase_service.setup_database()
        return {
            "success": True,
            "message": "Estado de la configuración de la base de datos",
            "results": results
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Error en setup de la base de datos"
        )
