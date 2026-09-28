-- Agrega el número de registro único a los reportes de incidentes.
-- Correr una sola vez en el SQL Editor de Supabase.

ALTER TABLE incident_reports
    ADD COLUMN IF NOT EXISTS numero_registro TEXT;

CREATE INDEX IF NOT EXISTS idx_incident_reports_numero_registro
    ON incident_reports (numero_registro);
