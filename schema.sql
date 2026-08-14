-- Enable pgvector extension if not already enabled (requires CockroachDB 24.1+)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS hive_context (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    context_type VARCHAR(50) NOT NULL, -- 'convention', 'architecture_decision', 'post_mortem', or 'infrastructure_context'
    topic VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR, -- Cast to the active deployment dimension by the vector index
    embedding_provider VARCHAR(50),
    embedding_model VARCHAR(100),
    embedding_dimensions INT,
    author VARCHAR(100),
    author_role VARCHAR(50) DEFAULT 'agent',
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- 'pending', 'approved', 'auto_approved', 'rejected', 'disabled', or 'deleted'
    retrieval_count INT DEFAULT 0,
    confidence_score INT DEFAULT 5,
    scope VARCHAR(20) DEFAULT 'global',
    project_name VARCHAR(100),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT current_timestamp(),
    deleted_at TIMESTAMP
);

-- Active Gemini deployment index. Change this only with embedding_models.py and
-- re-embed existing data before applying the corresponding migration.
CREATE INDEX IF NOT EXISTS hive_context_embedding_idx
    ON hive_context USING hnsw ((embedding::vector(3072)) vector_cosine_ops);

CREATE TABLE IF NOT EXISTS embedding_reembed_job (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status VARCHAR(30) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    dimensions INT NOT NULL,
    total_count INT NOT NULL DEFAULT 0,
    processed_count INT NOT NULL DEFAULT 0,
    failed_count INT NOT NULL DEFAULT 0,
    last_memory_id UUID,
    error_message TEXT,
    started_at TIMESTAMP DEFAULT current_timestamp(),
    completed_at TIMESTAMP
);
