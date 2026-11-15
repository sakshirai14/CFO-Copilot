-- migrations/007_embedding_dimension.sql
-- Foundation Locks 5 & 7: Update vector dimension to 384 for selected embedding model (BAAI/bge-small-en-v1.5)
-- and configure HNSW index for sub-5ms cosine similarity search.

ALTER TABLE chunks ALTER COLUMN embedding TYPE vector(384);

CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw 
ON chunks USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
