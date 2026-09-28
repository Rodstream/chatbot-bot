from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.services.embeddings_service import embeddings_service
from app.api.auth import get_current_user
from typing import List

router = APIRouter(prefix="/api/embeddings", tags=["Embeddings"])


class EmbeddingRequest(BaseModel):
    text: str

    @property
    def safe_text(self) -> str:
        return self.text[:8000].strip() if self.text else ""


class EmbeddingBatchRequest(BaseModel):
    texts: List[str]


class SimilarityRequest(BaseModel):
    text1: str
    text2: str


@router.post("/generate")
async def generate_embedding(request: EmbeddingRequest, user: dict = Depends(get_current_user)):
    """
    Genera el embedding para un texto
    """
    try:
        embedding = embeddings_service.generate_embedding(request.safe_text)

        return {
            "success": True,
            "text": request.safe_text,
            "embedding": embedding,
            "dimension": len(embedding),
            "preview": embedding[:5]  # Mostrar solo los primeros 5 valores
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail="Error interno")


@router.post("/generate-batch")
async def generate_embeddings_batch(request: EmbeddingBatchRequest, user: dict = Depends(get_current_user)):
    """
    Genera embeddings para múltiples textos
    """
    if len(request.texts) > 100:
        raise HTTPException(status_code=400, detail="Máximo 100 textos por lote")

    # Truncar cada texto a 8000 chars
    safe_texts = [t[:8000].strip() for t in request.texts if t]

    try:
        embeddings = embeddings_service.generate_embeddings_batch(safe_texts)

        return {
            "success": True,
            "count": len(embeddings),
            "dimension": len(embeddings[0]) if embeddings else 0,
            "embeddings": embeddings,
            "preview": [emb[:5] for emb in embeddings]  # Primeros 5 valores de cada uno
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail="Error interno")


@router.post("/similarity")
async def compute_similarity(request: SimilarityRequest, user: dict = Depends(get_current_user)):
    """
    Calcula la similitud entre dos textos
    Útil para ver qué tan similar es una búsqueda con un resultado
    """
    try:
        # Generar embeddings (truncar a 8000 chars)
        safe_t1 = request.text1[:8000].strip() if request.text1 else ""
        safe_t2 = request.text2[:8000].strip() if request.text2 else ""
        emb1 = embeddings_service.generate_embedding(safe_t1)
        emb2 = embeddings_service.generate_embedding(safe_t2)

        # Calcular similitud
        similarity = embeddings_service.compute_similarity(emb1, emb2)

        return {
            "success": True,
            "text1": request.text1,
            "text2": request.text2,
            "similarity": similarity,
            "similarity_percentage": f"{similarity * 100:.2f}%",
            "interpretation": "Muy similar" if similarity > 0.8 else
                            "Similar" if similarity > 0.6 else
                            "Algo relacionado" if similarity > 0.4 else
                            "Poco relacionado"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail="Error interno")


@router.get("/info")
async def get_model_info(user: dict = Depends(get_current_user)):
    """
    Información sobre el modelo de embeddings cargado
    """
    try:
        return {
            "success": True,
            "model": "BAAI/bge-m3",
            "dimension": embeddings_service.get_embedding_dimension(),
            "features": [
                "Multilingüe (español, inglés, etc.)",
                "Optimizado para RAG",
                "1024 dimensiones",
                "Procesamiento local (gratis)"
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail="Error interno")
