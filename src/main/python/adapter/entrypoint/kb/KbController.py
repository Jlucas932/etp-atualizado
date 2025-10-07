from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
import os
import hashlib
import PyPDF2
import pdfplumber
import logging
from domain.interfaces.dataprovider.DatabaseConfig import db
from domain.dto.KbDto import KbDocument, KbChunk
from datetime import datetime
import json

# Blueprint para endpoints de knowledge base
kb_blueprint = Blueprint('kb', __name__, url_prefix='/api/kb')

# Configure logging
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    """Verifica se o arquivo é permitido"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(file_path):
    """Extrai texto de um arquivo PDF usando pdfplumber"""
    text = []
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:  # Skip pages with no text
                    text.append(page_text)
    except Exception as e:
        logger.error("Erro ao extrair texto do PDF: %s", e, exc_info=True)
        return None
    return "\n".join(text) if text else None

def chunk_text(text, chunk_size=1000, overlap=200):
    """Divide o texto em chunks com sobreposição"""
    chunks = []
    text_length = len(text)
    
    for i in range(0, text_length, chunk_size - overlap):
        chunk = text[i:i + chunk_size]
        if chunk.strip():
            chunks.append(chunk.strip())
        
        if i + chunk_size >= text_length:
            break
    
    return chunks

def process_single_pdf(file, objective_slug):
    """Process a single PDF file and return result data"""
    if not allowed_file(file.filename):
        raise ValueError(f"Tipo de arquivo não permitido: {file.filename}. Apenas PDFs são aceitos.")
    
    # Salvar arquivo temporariamente
    filename = secure_filename(file.filename)
    temp_path = f"/tmp/{filename}"
    file.save(temp_path)
    
    try:
        # Extrair texto do PDF
        extracted_text = extract_text_from_pdf(temp_path)
        if not extracted_text:
            raise ValueError(f"Não foi possível extrair texto do PDF: {filename}")
        
        # Criar documento na base de conhecimento
        kb_doc = KbDocument(
            filename=filename,
            objective_slug=objective_slug,
            created_at=datetime.utcnow()
        )
        
        db.session.add(kb_doc)
        db.session.flush()  # Para obter o ID
        
        # Dividir texto em chunks e salvar
        chunks = chunk_text(extracted_text)
        chunk_count = 0
        
        for text_chunk in chunks:
            kb_chunk = KbChunk(
                kb_document_id=kb_doc.id,
                section_type='content',
                content_text=text_chunk,
                objective_slug=objective_slug,
                created_at=datetime.utcnow()
            )
            db.session.add(kb_chunk)
            chunk_count += 1
        
        logger.info(f"Processed PDF: {filename} - Document ID: {kb_doc.id} - Chunks: {chunk_count}")
        
        return {
            'filename': filename,
            'document_id': kb_doc.id,
            'chunks_created': chunk_count
        }
        
    finally:
        # Remover arquivo temporário
        if os.path.exists(temp_path):
            os.remove(temp_path)

@kb_blueprint.route("/upload", methods=["POST"])
def upload_pdf():
    """
    Upload e processamento de PDF(s) para knowledge base.
    
    Aceita múltiplos arquivos via 'file' no form-data.
    
    Returns:
        JSON: Estrutura com message e documents array contendo informações de cada arquivo processado
    """
    try:
        objective_slug = request.form.get('objective_slug', 'default')
        
        # Verificar se foi enviado arquivo
        files = request.files.getlist("file")
        if not files or not any(f.filename for f in files):
            return jsonify({"error": "Nenhum arquivo enviado"}), 400
        
        # Filtrar arquivos válidos
        files_to_process = [f for f in files if f.filename and f.filename != '']
        if not files_to_process:
            return jsonify({"error": "Nenhum arquivo enviado"}), 400
        
        # Validar que todos os arquivos são PDFs antes de processar
        for file in files_to_process:
            if not allowed_file(file.filename):
                return jsonify({"error": f"Arquivo {file.filename} não é um PDF válido. Apenas arquivos .pdf são aceitos."}), 400
        
        # Processar todos os arquivos
        docs_info = []
        for f in files_to_process:
            try:
                result = process_single_pdf(f, objective_slug)
                docs_info.append(result)
            except ValueError as ve:
                db.session.rollback()
                return jsonify({"error": str(ve)}), 400
            except Exception as e:
                db.session.rollback()
                logger.error(f"Erro ao processar arquivo {f.filename}: {e}")
                return jsonify({"error": f"Erro ao processar arquivo {f.filename}"}), 500
        
        db.session.commit()
        
        return jsonify({"message": "PDF processado com sucesso", "documents": docs_info}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro no upload de PDFs: {e}")
        return jsonify({"error": "Erro interno do servidor"}), 500

@kb_blueprint.route('/documents', methods=['GET'])
def list_documents():
    """Lista documentos na knowledge base"""
    try:
        objective_slug = request.args.get('objective_slug')
        
        query = KbDocument.query
        if objective_slug:
            query = query.filter_by(objective_slug=objective_slug)
        
        documents = query.order_by(KbDocument.created_at.desc()).all()
        
        return jsonify({
            'documents': [doc.to_dict() for doc in documents]
        }), 200
        
    except Exception as e:
        logger.error("Erro ao listar documentos: %s", e, exc_info=True)
        return jsonify({'error': 'Erro interno do servidor'}), 500

@kb_blueprint.route('/search', methods=['POST'])
def search_chunks():
    """Busca chunks relevantes na knowledge base"""
    try:
        data = request.get_json()
        query_text = data.get('query', '')
        objective_slug = data.get('objective_slug')
        limit = data.get('limit', 5)
        
        if not query_text:
            return jsonify({'error': 'Query text é obrigatório'}), 400
        
        # Busca simples por texto (sem embeddings por enquanto)
        chunks_query = KbChunk.query.filter(
            KbChunk.content_text.contains(query_text)
        )
        
        if objective_slug:
            chunks_query = chunks_query.filter_by(objective_slug=objective_slug)
        
        chunks = chunks_query.limit(limit).all()
        
        return jsonify({
            'chunks': [chunk.to_dict() for chunk in chunks],
            'total': len(chunks)
        }), 200
        
    except Exception as e:
        logger.error("Erro na busca de chunks: %s", e, exc_info=True)
        return jsonify({'error': 'Erro interno do servidor'}), 500

@kb_blueprint.route('/health', methods=['GET'])
def health_check():
    """Health check para o módulo KB"""
    try:
        # Verificar se consegue acessar o banco
        doc_count = KbDocument.query.count()
        chunk_count = KbChunk.query.count()
        
        return jsonify({
            'status': 'healthy',
            'documents_count': doc_count,
            'chunks_count': chunk_count
        }), 200
        
    except Exception as e:
        logger.error("Erro no health check KB: %s", e, exc_info=True)
        return jsonify({'error': 'Erro interno do servidor'}), 500