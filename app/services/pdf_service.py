from typing import List, Dict, Optional
import logging
from pathlib import Path
import gc
import os
import json
import subprocess
import sys

logger = logging.getLogger(__name__)

# Timeout para el worker (segundos)
WORKER_TIMEOUT = 60


class PDFService:
    """
    Servicio para procesar archivos PDF usando PyMuPDF
    Optimizado para bajo consumo de memoria
    """

    def __init__(self):
        pass

    def extract_text_from_pdf(self, pdf_path: str) -> List[Dict[str, any]]:
        """
        Extrae texto de un PDF usando un subproceso separado.
        Si el PDF causa problemas de memoria, el subproceso muere
        pero el servidor principal sigue funcionando.
        """
        logger.info(f"Procesando PDF en subproceso: {pdf_path}")

        # Ruta al worker
        worker_path = Path(__file__).parent / "pdf_worker.py"

        try:
            # Ejecutar worker en subproceso con timeout
            result = subprocess.run(
                [sys.executable, str(worker_path), pdf_path],
                capture_output=True,
                text=True,
                timeout=WORKER_TIMEOUT
            )

            if result.returncode != 0:
                error_msg = result.stderr or "Error desconocido en worker"
                logger.error(f"Worker falló: {error_msg}")
                raise Exception(f"Error procesando PDF: {error_msg}")

            # Parsear resultado JSON
            data = json.loads(result.stdout)

            if not data.get("success"):
                raise Exception(data.get("error", "Error desconocido"))

            # Convertir al formato esperado
            pages_data = []
            for page in data.get("pages", []):
                pages_data.append({
                    "page_number": page["page_number"],
                    "text": page["text"],
                    "char_count": len(page["text"])
                })

            logger.info(f"Extraidas {len(pages_data)} paginas (de {data.get('total_pages', '?')} totales)")
            return pages_data

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout procesando PDF ({WORKER_TIMEOUT}s)")
            raise Exception(f"El PDF tardó demasiado en procesar (>{WORKER_TIMEOUT}s)")

        except json.JSONDecodeError as e:
            logger.error(f"Error parseando respuesta del worker: {e}")
            raise Exception("Error interno procesando PDF")

        except Exception as e:
            logger.error(f"Error al procesar PDF: {str(e)}")
            raise

    def split_text_into_chunks(
        self,
        text: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> List[str]:
        """
        Divide un texto largo en chunks con overlap para mantener contexto

        Args:
            text: Texto a dividir
            chunk_size: Tamaño máximo de cada chunk en caracteres
            chunk_overlap: Cantidad de caracteres que se solapan entre chunks

        Returns:
            Lista de chunks de texto
        """
        if not text or len(text) <= chunk_size:
            return [text] if text else []

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            # Si no es el último chunk, intentar cortar en un punto natural
            if end < len(text):
                for separator in ['\n\n', '. ', '\n', ' ']:
                    last_sep = text.rfind(separator, start, end)
                    if last_sep != -1:
                        end = last_sep + len(separator)
                        break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Mover el inicio considerando el overlap
            start = end - chunk_overlap if end < len(text) else end

        return chunks

    def process_pdf_to_chunks(
        self,
        pdf_path: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        source_metadata: Optional[Dict] = None
    ) -> List[Dict[str, any]]:
        """
        Procesa un PDF completo y lo divide en chunks listos para embeddings

        Args:
            pdf_path: Ruta al PDF
            chunk_size: Tamaño de cada chunk
            chunk_overlap: Overlap entre chunks
            source_metadata: Metadatos adicionales

        Returns:
            Lista de diccionarios con chunks y sus metadatos
        """
        # Extraer texto del PDF
        pages = self.extract_text_from_pdf(pdf_path)

        # Obtener nombre del archivo
        filename = Path(pdf_path).name

        all_chunks = []
        chunk_global_index = 0

        for page_data in pages:
            # Dividir cada página en chunks
            page_chunks = self.split_text_into_chunks(
                page_data["text"],
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )

            # Agregar metadatos a cada chunk
            for chunk_index, chunk_text in enumerate(page_chunks):
                chunk_global_index += 1

                chunk_data = {
                    "content": chunk_text,
                    "source": filename,
                    "page_number": page_data["page_number"],
                    "chunk_index": chunk_global_index,
                    "chunk_in_page": chunk_index + 1,
                    "metadata": {
                        "char_count": len(chunk_text),
                        "original_page_chars": page_data["char_count"],
                        **(source_metadata or {})
                    }
                }

                all_chunks.append(chunk_data)

        logger.info(f"PDF procesado: {len(all_chunks)} chunks desde {len(pages)} paginas")

        # Liberar memoria
        gc.collect()

        return all_chunks


# Instancia global del servicio
pdf_service = PDFService()
