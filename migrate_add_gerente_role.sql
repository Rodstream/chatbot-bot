-- Permite el rol "gerente" en la tabla users.
-- Correr una sola vez en el SQL Editor de Supabase.

ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;

ALTER TABLE users
    ADD CONSTRAINT users_role_check CHECK (role IN ('admin', 'gerente', 'user'));
