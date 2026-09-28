-- Script de configuración para Supabase
-- Ejecutar este script en: SQL Editor de Supabase

-- 1. Activar la extensión pgvector (para búsqueda vectorial)
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Crear tabla para almacenar documentos y sus embeddings
CREATE TABLE IF NOT EXISTS documents (
    id BIGSERIAL PRIMARY KEY,
    content TEXT NOT NULL,                    -- Texto del chunk del documento
    embedding VECTOR(1536),                   -- Vector de embeddings (1536 dimensiones para OpenAI)
    metadata JSONB DEFAULT '{}'::jsonb,       -- Metadatos del documento
    source VARCHAR(500),                      -- Nombre del archivo fuente
    document_type VARCHAR(100),               -- Tipo: 'procedimiento', 'parte_diario', etc.
    obra VARCHAR(200),                        -- Nombre de la obra (si aplica)
    fecha DATE,                               -- Fecha del documento
    page_number INTEGER,                      -- Número de página en el PDF
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Crear índice para búsqueda vectorial (HNSW es más eficiente que IVFFlat)
CREATE INDEX IF NOT EXISTS documents_embedding_idx
ON documents
USING hnsw (embedding vector_cosine_ops);

-- 4. Crear índices para búsquedas frecuentes
CREATE INDEX IF NOT EXISTS documents_source_idx ON documents(source);
CREATE INDEX IF NOT EXISTS documents_type_idx ON documents(document_type);
CREATE INDEX IF NOT EXISTS documents_obra_idx ON documents(obra);
CREATE INDEX IF NOT EXISTS documents_fecha_idx ON documents(fecha);

-- 5. Crear función para búsqueda por similitud
CREATE OR REPLACE FUNCTION match_documents(
    query_embedding VECTOR(1536),
    match_threshold FLOAT DEFAULT 0.7,
    match_count INT DEFAULT 5
)
RETURNS TABLE (
    id BIGINT,
    content TEXT,
    metadata JSONB,
    source VARCHAR(500),
    document_type VARCHAR(100),
    obra VARCHAR(200),
    fecha DATE,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        documents.id,
        documents.content,
        documents.metadata,
        documents.source,
        documents.document_type,
        documents.obra,
        documents.fecha,
        1 - (documents.embedding <=> query_embedding) AS similarity
    FROM documents
    WHERE 1 - (documents.embedding <=> query_embedding) > match_threshold
    ORDER BY documents.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- 6. Confirmar que todo se creó correctamente
SELECT 'Setup completado correctamente!' AS status;
