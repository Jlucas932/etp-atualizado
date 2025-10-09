-- Inicialização do banco de dados AZ ETP
-- Versão simplificada sem schema específico

-- Criar extensões necessárias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Tabela para sessões de chat
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) UNIQUE NOT NULL,
    session_type VARCHAR(50) NOT NULL DEFAULT 'chat', -- 'chat' ou 'etp'
    title VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'active' -- 'active', 'completed', 'error'
);

-- Tabela para mensagens dos chats
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL, -- 'user' ou 'assistant'
    content TEXT NOT NULL,
    message_order INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE
);

-- Tabela para documentos ETP gerados
CREATE TABLE IF NOT EXISTS etp_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) NOT NULL,
    document_name VARCHAR(500),
    document_path VARCHAR(1000),
    document_content TEXT,
    answers JSONB, -- Armazenar respostas do questionário ETP
    generation_status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'generating', 'completed', 'error'
    generation_progress INTEGER DEFAULT 0, -- 0-100
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE
);

-- Tabela para progresso de geração de ETP
CREATE TABLE IF NOT EXISTS etp_generation_progress (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) NOT NULL,
    step_name VARCHAR(200) NOT NULL,
    step_order INTEGER NOT NULL,
    progress_percentage INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'error'
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE
);

-- Índices para melhor performance
CREATE INDEX IF NOT EXISTS idx_chat_sessions_session_id ON chat_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_created_at ON chat_sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_order ON chat_messages(session_id, message_order);
CREATE INDEX IF NOT EXISTS idx_etp_documents_session_id ON etp_documents(session_id);
CREATE INDEX IF NOT EXISTS idx_etp_progress_session_id ON etp_generation_progress(session_id);

-- Função para atualizar timestamp de updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger para atualizar updated_at automaticamente
CREATE TRIGGER update_chat_sessions_updated_at 
    BEFORE UPDATE ON chat_sessions 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

COMMIT;

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    documents_generated INT DEFAULT 0,
    chat_messages_sent INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);