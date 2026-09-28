"""
Test de procesamiento de PDF paso a paso
"""
import os
import sys
import psutil
from dotenv import load_dotenv

load_dotenv()

process = psutil.Process(os.getpid())
def get_memory_mb():
    return process.memory_info().rss / 1024 / 1024

print(f"Memoria inicial: {get_memory_mb():.1f} MB")

# Pedir ruta del PDF
pdf_path = input("\nIngresá la ruta completa del PDF a probar (o arrastralo aquí): ").strip().strip('"')

if not os.path.exists(pdf_path):
    print(f"❌ No se encontró el archivo: {pdf_path}")
    sys.exit(1)

file_size = os.path.getsize(pdf_path) / 1024 / 1024
print(f"\nArchivo: {os.path.basename(pdf_path)}")
print(f"Tamaño: {file_size:.2f} MB")

# Paso 1: Abrir PDF con pdfplumber
print(f"\n[1] Abriendo PDF con pdfplumber...")
import pdfplumber

try:
    with pdfplumber.open(pdf_path) as pdf:
        num_pages = len(pdf.pages)
        print(f"    Páginas: {num_pages}")
        print(f"    Memoria: {get_memory_mb():.1f} MB")

        # Paso 2: Extraer texto página por página
        print(f"\n[2] Extrayendo texto...")
        all_text = []
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            all_text.append(text)
            if (i + 1) % 5 == 0:
                print(f"    Página {i+1}/{num_pages} - Memoria: {get_memory_mb():.1f} MB")

        total_chars = sum(len(t) for t in all_text)
        print(f"    Total caracteres: {total_chars}")
        print(f"    Memoria después de extracción: {get_memory_mb():.1f} MB")

except Exception as e:
    print(f"❌ Error al procesar PDF: {e}")
    sys.exit(1)

# Paso 3: Dividir en chunks
print(f"\n[3] Dividiendo en chunks...")
chunks = []
for page_text in all_text:
    # Chunks de 1000 caracteres
    for i in range(0, len(page_text), 800):
        chunk = page_text[i:i+1000]
        if chunk.strip():
            chunks.append(chunk)

print(f"    Total chunks: {len(chunks)}")
print(f"    Memoria: {get_memory_mb():.1f} MB")

# Paso 4: Generar embeddings con OpenAI (solo primeros 5 para probar)
print(f"\n[4] Generando embeddings con OpenAI (primeros 5 chunks)...")
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

test_chunks = chunks[:5]
try:
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=test_chunks
    )
    print(f"    ✅ Embeddings generados: {len(response.data)}")
    print(f"    Dimensión: {len(response.data[0].embedding)}")
    print(f"    Memoria: {get_memory_mb():.1f} MB")
except Exception as e:
    print(f"    ❌ Error: {e}")

print(f"\n{'='*50}")
print(f"MEMORIA FINAL: {get_memory_mb():.1f} MB")
print(f"{'='*50}")

if get_memory_mb() > 500:
    print("\n⚠️  Algo está consumiendo demasiada memoria")
else:
    print("\n✅ El procesamiento de PDF funciona correctamente")
    print("\nEl problema podría estar en:")
    print("  - La conexión con Supabase")
    print("  - La inserción de datos")
    print("  - El endpoint async de FastAPI")
