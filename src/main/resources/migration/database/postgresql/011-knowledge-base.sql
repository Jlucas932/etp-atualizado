-- ================================================
-- Changeset 011: Knowledge Base Tables Creation
-- Description: Creates tables for knowledge base management
-- Tables: kb_document, kb_chunk, legal_norm_cache
-- ================================================

-- create tables section -------------------------------------------------

-- table kb_document
CREATE TABLE kb_document
(
    id serial NOT NULL,
    filename varchar(255) NOT NULL,
    etp_id integer,
    objective_slug varchar(100) NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);

-- table kb_chunk  
CREATE TABLE kb_chunk
(
    id serial NOT NULL,
    kb_document_id integer NOT NULL,
    section_type varchar(50) NOT NULL,
    content_text text NOT NULL,
    objective_slug varchar(100) NOT NULL,
    citations_json text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);

-- table legal_norm_cache
CREATE TABLE legal_norm_cache
(
    id serial NOT NULL,
    norm_urn varchar(500) NOT NULL,
    norm_label varchar(1000) NOT NULL,
    sphere varchar(50) NOT NULL,
    status varchar(50) NOT NULL,
    source_json text,
    last_verified_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);

-- create primary keys section -------------------------------------------------

ALTER TABLE kb_document
    ADD CONSTRAINT pk_kb_document PRIMARY KEY (id);

ALTER TABLE kb_chunk
    ADD CONSTRAINT pk_kb_chunk PRIMARY KEY (id);

ALTER TABLE legal_norm_cache
    ADD CONSTRAINT pk_legal_norm_cache PRIMARY KEY (id);

-- create unique constraints section -------------------------------------------------

ALTER TABLE legal_norm_cache
    ADD CONSTRAINT uk_legal_norm_cache_urn UNIQUE (norm_urn);

-- create foreign keys (relationships) section -------------------------------------------------

ALTER TABLE kb_document
    ADD CONSTRAINT fk_kb_document_etp_session
        FOREIGN KEY (etp_id) REFERENCES etp_sessions (id)
        ON DELETE SET NULL;

ALTER TABLE kb_chunk
    ADD CONSTRAINT fk_kb_chunk_document
        FOREIGN KEY (kb_document_id) REFERENCES kb_document (id)
        ON DELETE CASCADE;

-- create indexes section -------------------------------------------------

-- Indexes for kb_document
CREATE INDEX idx_kb_document_objective_slug ON kb_document (objective_slug);
CREATE INDEX idx_kb_document_etp_id ON kb_document (etp_id);
CREATE INDEX idx_kb_document_created_at ON kb_document (created_at);

-- Indexes for kb_chunk
CREATE INDEX idx_kb_chunk_document_id ON kb_chunk (kb_document_id);
CREATE INDEX idx_kb_chunk_section_type ON kb_chunk (section_type);
CREATE INDEX idx_kb_chunk_objective_slug ON kb_chunk (objective_slug);
CREATE INDEX idx_kb_chunk_created_at ON kb_chunk (created_at);

-- Indexes for legal_norm_cache
CREATE INDEX idx_legal_norm_cache_sphere ON legal_norm_cache (sphere);
CREATE INDEX idx_legal_norm_cache_status ON legal_norm_cache (status);
CREATE INDEX idx_legal_norm_cache_last_verified ON legal_norm_cache (last_verified_at);
CREATE INDEX idx_legal_norm_cache_norm_urn ON legal_norm_cache (norm_urn);

-- create comments section -------------------------------------------------

COMMENT ON TABLE kb_document IS 'Documents in the knowledge base system';
COMMENT ON COLUMN kb_document.id IS 'Primary key identifier';
COMMENT ON COLUMN kb_document.filename IS 'Original filename of the document';
COMMENT ON COLUMN kb_document.etp_id IS 'Reference to ETP session that generated this document';
COMMENT ON COLUMN kb_document.objective_slug IS 'Objective category slug for document classification';
COMMENT ON COLUMN kb_document.created_at IS 'Timestamp when the document was created';

COMMENT ON TABLE kb_chunk IS 'Text chunks extracted from knowledge base documents';
COMMENT ON COLUMN kb_chunk.id IS 'Primary key identifier';
COMMENT ON COLUMN kb_chunk.kb_document_id IS 'Reference to parent document';
COMMENT ON COLUMN kb_chunk.section_type IS 'Type of document section (requirement, legal_norm, etc.)';
COMMENT ON COLUMN kb_chunk.content_text IS 'Actual text content of the chunk';
COMMENT ON COLUMN kb_chunk.objective_slug IS 'Objective category for chunk classification';
COMMENT ON COLUMN kb_chunk.citations_json IS 'JSON data containing citations and references';
COMMENT ON COLUMN kb_chunk.created_at IS 'Timestamp when the chunk was created';

COMMENT ON TABLE legal_norm_cache IS 'Cache of legal norms and their metadata';
COMMENT ON COLUMN legal_norm_cache.id IS 'Primary key identifier';
COMMENT ON COLUMN legal_norm_cache.norm_urn IS 'Unique Resource Name for the legal norm';
COMMENT ON COLUMN legal_norm_cache.norm_label IS 'Human-readable label for the norm';
COMMENT ON COLUMN legal_norm_cache.sphere IS 'Government sphere (federal, estadual, municipal)';
COMMENT ON COLUMN legal_norm_cache.status IS 'Current status (active, revoked, modified)';
COMMENT ON COLUMN legal_norm_cache.source_json IS 'JSON data from the source system';
COMMENT ON COLUMN legal_norm_cache.last_verified_at IS 'Last time this norm was verified';