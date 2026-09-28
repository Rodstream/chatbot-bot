# Chatbot RAG — Backend

Backend de un chatbot conversacional con RAG (Retrieval-Augmented Generation) para consultar documentación interna de una empresa (procedimientos, instructivos, manuales) y registrar reportes de incidentes desde el chat.

## Stack Técnico
- Python 3.10+
- FastAPI
- Supabase (PostgreSQL + pgvector)
- Claude API (Anthropic) — generación de respuestas
- OpenAI — embeddings para búsqueda semántica

## Funcionalidad

- Búsqueda semántica sobre documentos cargados (PDF, Word, Excel), con filtros por tipo de documento, obra y fecha.
- Respuestas en streaming (SSE) citando la fuente del documento consultado.
- Roles de usuario (admin / usuario) con distintos niveles de acceso a documentación y administración.
- Carga de reportes de incidentes desde el chat, con numeración secuencial automática, generación de PDF y envío por mail al responsable de seguimiento.
- Respaldo automático de reportes y adjuntos en Google Drive.
- Autenticación con sesiones firmadas (HMAC) y contraseñas con hash PBKDF2.

## Instalación

### 1. Crear entorno virtual
```bash
python -m venv venv
```

### 2. Activar entorno virtual
**Windows (Git Bash/MinGW):**
```bash
source venv/Scripts/activate
```

**Windows (CMD):**
```bash
venv\Scripts\activate.bat
```

**Windows (PowerShell):**
```bash
venv\Scripts\Activate.ps1
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno
```bash
cp .env.example .env
# Editar .env con tus credenciales
```

### 5. Correr en local
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Estructura del Proyecto

```
backend/
├── app/
│   ├── api/          # Endpoints de la API
│   ├── core/         # Configuración central
│   ├── services/     # Lógica de negocio (Claude, embeddings, mail, Drive, etc.)
│   ├── models/       # Modelos de datos
│   └── utils/        # Utilidades generales
├── tests/            # Tests automatizados
├── .env.example      # Template de variables de entorno
├── render.yaml        # Configuración de deploy (Render)
├── requirements.txt  # Dependencias Python
└── README.md         # Este archivo
```

## Tests
```bash
python -m pytest tests/ -q
```
