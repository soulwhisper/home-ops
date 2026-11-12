-- Runs once, on the empty data directory created by this stack.
-- The cluster ensured these through a CNPG Database CR; on the NAS the
-- extensions come from the image and are created here.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgroonga;
