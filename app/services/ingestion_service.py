from app.services.pdf_service import pdf_service
from app.services.embeddings_service import embeddings_service
from app.services.supabase_service import supabase_service
from typing import Dict, Optional
from datetime import datetime
import logging
import gc

logger = logging.getLogger(__name__)

# Limites para evitar problemas de memoria
MAX_CHUNKS = 500  # Maximo chunks por PDF
BATCH_SIZE = 50   # Procesar de a 50 chunks


class IngestionService:
    """
    Servicio para ingerir documentos PDF al sistema RAG
    Optimizado para bajo consumo de memoria
    """

    def __init__(self):
        self.pdf_service = pdf_service
        self.embeddings_service = embeddings_service
        self.supabase = supabase_service.get_client()

    async def ingest_pdf(
        self,
        pdf_path: str,
        document_type: str = "documento",
        obra: Optional[str] = None,
        fecha: Optional[datetime] = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> Dict:
        """
        Ingesta de PDF optimizada - procesa e inserta en batches pequeños
        """
        try:
            logger.info(f"Iniciando ingesta de PDF: {pdf_path}")

            # 1. Procesar PDF a chunks
            metadata = {
                "document_type": document_type,
                "obra": obra,
                "fecha": fecha.isoformat() if fecha else None
            }

            chunks = self.pdf_service.process_pdf_to_chunks(
                pdf_path=pdf_path,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                source_metadata=metadata
            )

            total_chunks = len(chunks)
            logger.info(f"PDF procesado: {total_chunks} chunks")

            # Limitar chunks
            if total_chunks > MAX_CHUNKS:
                logger.warning(f"Limitando de {total_chunks} a {MAX_CHUNKS} chunks")
                chunks = chunks[:MAX_CHUNKS]
                total_chunks = MAX_CHUNKS

            # 2. Procesar e insertar en batches pequeños
            total_inserted = 0

            for i in range(0, total_chunks, BATCH_SIZE):
                batch_chunks = chunks[i:i + BATCH_SIZE]

                # Extraer textos del batch
                batch_texts = [c["content"] for c in batch_chunks]

                # Generar embeddings solo para este batch
                batch_embeddings = self.embeddings_service.generate_embeddings_batch(batch_texts)

                # Preparar documentos para insertar
                docs_to_insert = []
                for j, chunk in enumerate(batch_chunks):
                    doc = {
                        "content": chunk["content"],
                        "embedding": batch_embeddings[j],
                        "source": chunk["source"],
                        "page_number": chunk["page_number"],
                        "document_type": document_type,
                        "obra": obra,
                        "fecha": fecha.isoformat() if fecha else None,
                        "metadata": {
                            "chunk_index": chunk["chunk_index"],
                            "chunk_in_page": chunk["chunk_in_page"]
                        }
                    }
                    docs_to_insert.append(doc)

                # Insertar en Supabase
                self.supabase.table("documents").insert(docs_to_insert).execute()
                total_inserted += len(docs_to_insert)

                logger.info(f"Progreso: {total_inserted}/{total_chunks} chunks")

                # Liberar memoria
                del batch_embeddings
                del docs_to_insert
                del batch_texts
                gc.collect()

            # Liberar chunks de memoria
            del chunks
            gc.collect()

            logger.info(f"Ingesta completada: {total_inserted} chunks insertados")

            return {
                "success": True,
                "chunks_processed": total_inserted,
                "embeddings_generated": total_inserted,
                "documents_inserted": total_inserted
            }

        except Exception as e:
            logger.error(f"Error en ingesta: {str(e)}")
            gc.collect()
            raise Exception(f"Error al ingerir PDF: {str(e)}")

    async def get_documents_stats(self) -> Dict:
        """Obtiene estadisticas de documentos"""
        try:
            total = self.supabase.table("documents").select("id", count="exact").execute()

            return {
                "success": True,
                "total_documents": total.count if hasattr(total, 'count') else 0
            }

        except Exception as e:
            logger.error(f"Error obteniendo estadisticas: {str(e)}")
            return {"success": False, "error": "Error obteniendo estadísticas"}


# Instancia global
ingestion_service = IngestionService()
