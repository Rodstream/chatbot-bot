"""
Test simple para verificar que OpenAI embeddings funciona
"""
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")

print(f"API Key encontrada: {'Sí' if api_key else 'No'}")
print(f"API Key (primeros 10 chars): {api_key[:10] if api_key else 'N/A'}...")

if not api_key:
    print("\n❌ ERROR: No se encontró OPENAI_API_KEY en el archivo .env")
    print("Asegurate de tener esta línea en tu .env:")
    print("OPENAI_API_KEY=sk-tu-api-key-aqui")
    exit(1)

print("\nProbando conexión con OpenAI...")

try:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)

    # Test simple
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input="Hola mundo, esto es una prueba"
    )

    embedding = response.data[0].embedding

    print(f"\n✅ ÉXITO!")
    print(f"   Dimensión del embedding: {len(embedding)}")
    print(f"   Primeros 5 valores: {embedding[:5]}")
    print(f"\nOpenAI está funcionando correctamente.")

except Exception as e:
    print(f"\n❌ ERROR: {str(e)}")
    print("\nVerificá que tu API key sea válida en https://platform.openai.com/api-keys")
