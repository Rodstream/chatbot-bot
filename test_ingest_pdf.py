"""
Script de prueba para ingerir un PDF al sistema RAG

Uso:
    python test_ingest_pdf.py ruta/al/archivo.pdf
"""

import asyncio
import sys
from app.services.ingestion_service import ingestion_service
from datetime import datetime


async def test_ingest(pdf_path: str):
    """Prueba la ingesta de un PDF"""

    print(f"\n🔄 Iniciando ingesta de: {pdf_path}\n")

    try:
        result = await ingestion_service.ingest_pdf(
            pdf_path=pdf_path,
            document_type="procedimiento",
            obra="Obra de Prueba",
            fecha=datetime.now()
        )

        print("✅ INGESTA EXITOSA!")
        print(f"\n📊 Resultados:")
        print(f"   - Chunks procesados: {result['chunks_processed']}")
        print(f"   - Embeddings generados: {result['embeddings_generated']}")
        print(f"   - Documentos insertados: {result['documents_inserted']}")
        print(f"   - Tipo: {result['document_type']}")
        print(f"   - Obra: {result['obra']}")

        # Obtener estadísticas
        print(f"\n📈 Estadísticas de la base de datos:")
        stats = await ingestion_service.get_documents_stats()
        print(f"   - Total documentos: {stats.get('total_documents', 0)}")

    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        return False

    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ Uso: python test_ingest_pdf.py ruta/al/archivo.pdf")
        sys.exit(1)

    pdf_path = sys.argv[1]

    # Ejecutar la ingesta
    asyncio.run(test_ingest(pdf_path))
