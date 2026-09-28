from openai import OpenAI
import logging
from typing import List
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingsService:
    """
    Servicio para generar embeddings usando OpenAI API
    Modelo: text-embedding-3-small (1536 dimensiones)
    Costo: ~$0.02 por 1M tokens (muy económico)
    """

    def __init__(self):
        """Inicializa el cliente de OpenAI"""
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY no está configurada en .env")

        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "text-embedding-3-small"
        self.dimension = 1536
        logger.info(f"EmbeddingsService inicializado con modelo: {self.model}")

    def generate_embedding(self, text: str) -> List[float]:
        """
        Genera el embedding para un texto individual

        Args:
            text: Texto a convertir en embedding

        Returns:
            Lista de floats representando el vector embedding
        """
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text
            )
            return response.data[0].embedding

        except Exception as e:
            logger.error(f"Error al generar embedding: {str(e)}")
            raise Exception(f"Error generando embedding: {str(e)}")

    def generate_embeddings_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """
        Genera embeddings para múltiples textos

        Args:
            texts: Lista de textos a convertir
            batch_size: Tamaño del batch (OpenAI soporta hasta 2048)

        Returns:
            Lista de embeddings
        """
        try:
            logger.info(f"Generando embeddings para {len(texts)} textos")

            all_embeddings = []

            # Procesar en batches
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]

                response = self.client.embeddings.create(
                    model=self.model,
                    input=batch_texts
                )

                # Extraer embeddings en el orden correcto
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)

                logger.info(f"  Procesados {min(i + batch_size, len(texts))}/{len(texts)} embeddings")

            return all_embeddings

        except Exception as e:
            logger.error(f"Error al generar embeddings batch: {str(e)}")
            raise Exception(f"Error generando embeddings batch: {str(e)}")

    def get_embedding_dimension(self) -> int:
        """Retorna la dimensión de los embeddings (1536 para text-embedding-3-small)"""
        return self.dimension

    def compute_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calcula la similitud coseno entre dos embeddings

        Args:
            embedding1: Primer embedding
            embedding2: Segundo embedding

        Returns:
            Similitud coseno (0 a 1, donde 1 es idéntico)
        """
        import numpy as np

        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        similarity = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

        return float(similarity)


# Instancia global del servicio
embeddings_service = EmbeddingsService()
