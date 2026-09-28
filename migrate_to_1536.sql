-- MIGRACIÓN: Cambiar embeddings de 384/768/1024 a 1536 dimensiones (OpenAI)
-- Ejecutar en Supabase SQL Editor

-- 1. Borrar la tabla existente (perderás los datos anteriores)
DROP TABLE IF EXISTS documents CASCADE;

-- 2. Borrar función existente
DROP FUNCTION IF EXISTS match_documents;

-- 3. Recrear tabla con 1536 dimensiones
CREATE TABLE documents (
    id BIGSERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    embedding VECTOR(1536),                   -- OpenAI text-embedding-3-small
    metadata JSONB DEFAULT '{}'::jsonb,
    source VARCHAR(500),
    document_type VARCHAR(100),
    obra VARCHAR(200),
    fecha DATE,
    page_number INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Recrear índice vectorial
CREATE INDEX documents_embedding_idx
ON documents
USING hnsw (embedding vector_cosine_ops);

-- 5. Recrear otros índices
CREATE INDEX documents_source_idx ON documents(source);
CREATE INDEX documents_type_idx ON documents(document_type);
CREATE INDEX documents_obra_idx ON documents(obra);
CREATE INDEX documents_fecha_idx ON documents(fecha);

-- 6. Recrear función de búsqueda
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

SELECT 'Migración completada - Ahora usa 1536 dimensiones (OpenAI)' AS status;
