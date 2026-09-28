"""Test del worker directamente"""
import subprocess
import sys
import os

# Usar el test.pdf que ya está en backend
pdf_path = os.path.join(os.path.dirname(__file__), "test.pdf")

if not os.path.exists(pdf_path):
    print("ERROR: No existe test.pdf en la carpeta backend")
    print("Copia un PDF ahí y renombralo a test.pdf")
    sys.exit(1)

print(f"Probando con: {pdf_path}")
print("="*50)

worker = os.path.join(os.path.dirname(__file__), "app", "services", "ingest_worker.py")

result = subprocess.run(
    [sys.executable, worker, pdf_path, "test.pdf", "documento", "", ""],
    capture_output=True,
    text=True,
    timeout=60
)

print("STDOUT:")
print(result.stdout)
print("\nSTDERR:")
print(result.stderr)
print("\nReturn code:", result.returncode)
