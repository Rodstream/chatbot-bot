from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from app.services.search_service import search_service
from app.api.auth import get_current_user
from typing import Optional

router = APIRouter(prefix="/api/search", tags=["Search"])


class SearchRequest(BaseModel):
    query: str
    limit: int = 5
    similarity_threshold: float = 0.2  # Umbral bajo para mejor recall
    document_type: Optional[str] = None
    obra: Optional[str] = None
    fecha_desde: Optional[str] = None
    fecha_hasta: Optional[str] = None

    @property
    def safe_query(self) -> str:
        return self.query[:2000].strip() if self.query else ""


@router.post("/")
async def search_documents(request: SearchRequest, user: dict = Depends(get_current_user)):
    """
    Busca documentos relevantes usando búsqueda vectorial semántica

    Ejemplo de búsqueda:
    {
      "query": "¿Cómo se debe señalizar una obra en autopista?",
      "limit": 5,
      "similarity_threshold": 0.5
    }
    """
    # Validar parámetros
    if request.limit > 20:
        request.limit = 20
    if not (0.0 <= request.similarity_threshold <= 1.0):
        request.similarity_threshold = 0.2

    try:
        results = await search_service.search(
            query=request.safe_query,
            limit=request.limit,
            similarity_threshold=request.similarity_threshold,
            document_type=request.document_type,
            obra=request.obra,
            fecha_desde=request.fecha_desde,
            fecha_hasta=request.fecha_hasta
        )

        return {
            "success": True,
            "query": request.safe_query,
            "results_found": len(results),
            "results": results
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail="Error en la búsqueda")


@router.post("/with-context")
async def search_with_context(request: SearchRequest, user: dict = Depends(get_current_user)):
    """
    Busca documentos y retorna un contexto unificado listo para RAG

    Este endpoint es el que usaremos internamente para el chat con RAG
    """
    # Validar parámetros
    if request.limit > 20:
        request.limit = 20
    if not (0.0 <= request.similarity_threshold <= 1.0):
        request.similarity_threshold = 0.2

    try:
        result = await search_service.search_with_context(
            query=request.safe_query,
            limit=request.limit,
            similarity_threshold=request.similarity_threshold,
            document_type=request.document_type,
            obra=request.obra,
            fecha_desde=request.fecha_desde,
            fecha_hasta=request.fecha_hasta
        )

        return {
            "success": True,
            **result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail="Error en la búsqueda")


@router.get("/test")
async def test_search(
    q: str = Query(..., description="Texto a buscar"),
    limit: int = Query(3, description="Número de resultados"),
    user: dict = Depends(get_current_user)
):
    """
    Endpoint simple para probar búsquedas rápidas desde el navegador

    Ejemplo: /api/search/test?q=señalización&limit=3
    """
    try:
        results = await search_service.search(
            query=q,
            limit=limit,
            similarity_threshold=0.1  # Umbral bajo para testing
        )

        # Formato simplificado para lectura rápida
        simplified = []
        for doc in results:
            simplified.append({
                "source": doc.get('source'),
                "page": doc.get('page_number'),
                "similarity": f"{doc.get('similarity', 0):.2%}",
                "preview": doc.get('content', '')[:200] + "..."
            })

        return {
            "success": True,
            "query": q,
            "found": len(simplified),
            "results": simplified
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail="Error en la búsqueda")
