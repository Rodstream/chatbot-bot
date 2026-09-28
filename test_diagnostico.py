"""
Test de diagnóstico - prueba cada componente por separado
"""
import sys
import os

# Medir memoria inicial
import psutil
process = psutil.Process(os.getpid())

def get_memory_mb():
    return process.memory_info().rss / 1024 / 1024

print(f"Memoria inicial: {get_memory_mb():.1f} MB")

# Test 1: Cargar dotenv
print("\n[1] Cargando dotenv...")
from dotenv import load_dotenv
load_dotenv()
print(f"    Memoria después de dotenv: {get_memory_mb():.1f} MB")

# Test 2: Cargar OpenAI
print("\n[2] Cargando OpenAI...")
from openai import OpenAI
print(f"    Memoria después de OpenAI: {get_memory_mb():.1f} MB")

# Test 3: Cargar pdfplumber
print("\n[3] Cargando pdfplumber...")
import pdfplumber
print(f"    Memoria después de pdfplumber: {get_memory_mb():.1f} MB")

# Test 4: Cargar FastAPI
print("\n[4] Cargando FastAPI...")
from fastapi import FastAPI
print(f"    Memoria después de FastAPI: {get_memory_mb():.1f} MB")

# Test 5: Cargar Supabase
print("\n[5] Cargando Supabase...")
from supabase import create_client
print(f"    Memoria después de Supabase: {get_memory_mb():.1f} MB")

# Test 6: Cargar numpy
print("\n[6] Cargando numpy...")
import numpy as np
print(f"    Memoria después de numpy: {get_memory_mb():.1f} MB")

print("\n" + "="*50)
print(f"MEMORIA TOTAL USADA: {get_memory_mb():.1f} MB")
print("="*50)

if get_memory_mb() > 500:
    print("\n⚠️  ALERTA: Usando más de 500MB solo en imports")
else:
    print("\n✅ Memoria normal para los imports")

# Verificar si torch está instalado accidentalmente
print("\n[7] Verificando si torch está instalado...")
try:
    import torch
    print(f"    ⚠️  TORCH ESTÁ INSTALADO! Memoria: {get_memory_mb():.1f} MB")
    print("    Ejecutá: pip uninstall torch -y")
except ImportError:
    print("    ✅ torch NO está instalado (bien)")

# Verificar sentence-transformers
print("\n[8] Verificando sentence-transformers...")
try:
    import sentence_transformers
    print(f"    ⚠️  SENTENCE-TRANSFORMERS ESTÁ INSTALADO!")
    print("    Ejecutá: pip uninstall sentence-transformers -y")
except ImportError:
    print("    ✅ sentence-transformers NO está instalado (bien)")

print(f"\nMemoria final: {get_memory_mb():.1f} MB")
