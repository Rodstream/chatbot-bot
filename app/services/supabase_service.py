from supabase import create_client, Client
from app.core.config import settings
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class SupabaseService:
    """Servicio para interactuar con Supabase (PostgreSQL + pgvector)"""

    def __init__(self):
        """Inicializa el cliente de Supabase"""
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            raise ValueError("SUPABASE_URL y SUPABASE_KEY deben estar configuradas")

        self.client: Client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_KEY
        )
        logger.info("Cliente de Supabase inicializado correctamente")

    async def check_connection(self) -> bool:
        """
        Verifica que la conexión con Supabase funciona

        Returns:
            True si la conexión es exitosa
        """
        try:
            # Intenta hacer una query simple
            result = self.client.table("documents").select("count").limit(1).execute()
            return True
        except Exception as e:
            logger.error(f"Error al conectar con Supabase: {str(e)}")
            # Si la tabla no existe todavía, también es válido (solo estamos testeando conexión)
            if "relation" in str(e) and "does not exist" in str(e):
                return True
            return False

    async def setup_database(self) -> Dict[str, str]:
        """
        Configura la base de datos: activa pgvector y crea las tablas necesarias

        Returns:
            Dict con el resultado de cada operación
        """
        results = {}

        try:
            # 1. Activar extensión pgvector
            try:
                self.client.rpc("enable_pgvector").execute()
                results["pgvector"] = "Extensión pgvector activada"
            except Exception as e:
                # Si ya está activada, no es un error
                if "already exists" in str(e):
                    results["pgvector"] = "Extensión pgvector ya estaba activada"
                else:
                    results["pgvector"] = f"Error: {str(e)}"

            # 2. Crear tabla de documentos
            # Nota: Esto se hace mejor desde el SQL Editor de Supabase
            # Lo vamos a hacer en el siguiente paso con un script SQL
            results["table"] = "Pendiente de crear desde SQL Editor"

            return results

        except Exception as e:
            logger.error(f"Error en setup_database: {str(e)}")
            raise Exception(f"Error al configurar la base de datos: {str(e)}")

    def get_client(self) -> Client:
        """Retorna el cliente de Supabase para uso directo"""
        return self.client


# Instancia global del servicio
supabase_service = SupabaseService()
