"""
Test para encontrar donde esta el memory leak
Ejecutar: python test_memory_leak.py
"""
import os
import sys
import gc

# Medir memoria
import psutil
process = psutil.Process(os.getpid())

def get_mem():
    return process.memory_info().rss / 1024 / 1024

print(f"[INICIO] Memoria: {get_mem():.1f} MB")

# Cargar .env
from dotenv import load_dotenv
load_dotenv()
print(f"[dotenv] Memoria: {get_mem():.1f} MB")

# Usar test.pdf directamente
pdf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test.pdf")
print(f"\nBuscando: {pdf_path}")
if not os.path.exists(pdf_path):
    print("ERROR: No se encontro test.pdf en la carpeta backend")
    print("Copia el PDF problematico a la carpeta backend y renombralo a test.pdf")
    sys.exit(1)

print(f"\nArchivo: {os.path.basename(pdf_path)}")
print(f"Tamaño: {os.path.getsize(pdf_path) / 1024 / 1024:.2f} MB")

# PASO 1: Probar PyMuPDF
print(f"\n{'='*50}")
print("PASO 1: Extraer texto con PyMuPDF")
print(f"{'='*50}")
input("Presiona Enter para continuar...")

import fitz
mem_antes = get_mem()
print(f"Memoria antes de abrir PDF: {mem_antes:.1f} MB")

doc = fitz.open(pdf_path)
print(f"Paginas: {len(doc)}")
print(f"Memoria despues de abrir: {get_mem():.1f} MB")

textos = []
for i, page in enumerate(doc):
    texto = page.get_text()
    textos.append(texto)
    if (i + 1) % 10 == 0:
        print(f"  Pagina {i+1}: {get_mem():.1f} MB")

doc.close()
gc.collect()

print(f"Memoria despues de extraer texto: {get_mem():.1f} MB")
print(f"Total caracteres: {sum(len(t) for t in textos)}")

# PASO 2: Dividir en chunks
print(f"\n{'='*50}")
print("PASO 2: Dividir en chunks")
print(f"{'='*50}")
input("Presiona Enter para continuar...")

mem_antes = get_mem()
chunks = []
for texto in textos:
    for i in range(0, len(texto), 800):
        chunk = texto[i:i+1000]
        if chunk.strip():
            chunks.append(chunk)

print(f"Total chunks: {len(chunks)}")
print(f"Memoria despues de chunks: {get_mem():.1f} MB (delta: {get_mem() - mem_antes:.1f} MB)")

# Liberar textos originales
del textos
gc.collect()
print(f"Memoria despues de liberar textos: {get_mem():.1f} MB")

# PASO 3: Generar embeddings con OpenAI (solo 5 para probar)
print(f"\n{'='*50}")
print("PASO 3: Generar embeddings con OpenAI (5 chunks)")
print(f"{'='*50}")
input("Presiona Enter para continuar...")

from openai import OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

mem_antes = get_mem()
test_chunks = chunks[:5]

response = client.embeddings.create(
    model="text-embedding-3-small",
    input=test_chunks
)
embeddings = [item.embedding for item in response.data]

print(f"Embeddings generados: {len(embeddings)}")
print(f"Memoria despues de embeddings: {get_mem():.1f} MB (delta: {get_mem() - mem_antes:.1f} MB)")

del embeddings
del response
gc.collect()
print(f"Memoria despues de liberar: {get_mem():.1f} MB")

# PASO 4: Probar con MAS embeddings
print(f"\n{'='*50}")
print("PASO 4: Generar embeddings para TODOS los chunks (de a 5)")
print(f"{'='*50}")
print(f"Total chunks a procesar: {len(chunks)}")
respuesta = input("Continuar? (s/n): ")

if respuesta.lower() == 's':
    mem_antes = get_mem()
    total = 0

    for i in range(0, min(len(chunks), 50), 5):  # Maximo 50 chunks para test
        batch = chunks[i:i+5]
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=batch
        )
        total += len(response.data)

        # Liberar inmediatamente
        del response
        gc.collect()

        print(f"  Batch {i//5 + 1}: {get_mem():.1f} MB (procesados: {total})")

    print(f"\nMemoria final: {get_mem():.1f} MB (delta: {get_mem() - mem_antes:.1f} MB)")

print(f"\n{'='*50}")
print(f"MEMORIA FINAL: {get_mem():.1f} MB")
print(f"{'='*50}")

if get_mem() > 500:
    print("\n⚠️  La memoria sigue siendo alta. El problema puede estar en:")
    print("   - El PDF tiene contenido problematico (imagenes embebidas)")
    print("   - Algun memory leak en las librerias")
else:
    print("\n✅ La memoria esta normal. El problema puede estar en FastAPI/uvicorn")
