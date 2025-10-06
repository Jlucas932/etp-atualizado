"""
Módulo de ingestão de ETPs para o sistema RAG.
Lê arquivos JSONL de knowledge/etps/parsed/ e popula a base de conhecimento.
"""

import os
import sys
import json
import logging
import argparse
import uuid
from pathlib import Path
from typing import List, Dict, Optional
import numpy as np
import faiss
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import PyPDF2

# Adicionar src/main/python ao path para imports
current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

from domain.dto.KnowledgeBaseDto import KbDocument, KbChunk, KnowledgeBaseDocument
from domain.interfaces.dataprovider.DatabaseConfig import db

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ETPIngestor:
    """Classe para ingerir ETPs na base de conhecimento"""
    
    def __init__(self, openai_client = None):
        # Validar DATABASE_URL obrigatório
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is required for PostgreSQL connection")
        
        # Validar que é PostgreSQL
        if not database_url.startswith('postgresql'):
            raise ValueError(f"Only PostgreSQL is supported. Got: {database_url.split('://')[0]}")
        
        # Log da configuração (sem senha)
        masked_url = database_url.split('@')[0].split('://')
        if len(masked_url) > 1:
            masked_url = f"{masked_url[0]}://***@{database_url.split('@')[1]}"
        else:
            masked_url = "***"
        logger.info(f"🔗 DB URL (masked): {masked_url}")
        
        self.openai_client = openai_client
        self.embeddings_provider = os.getenv('EMBEDDINGS_PROVIDER', 'openai')
        
        # NÃO criar engine próprio - usar sempre o shared session do db
        
        # Diretórios
        self.project_root = Path(__file__).parent.parent.parent.parent.parent
        self.parsed_dir = self.project_root / "knowledge" / "etps" / "parsed"
        self.raw_pdfs_dir = self.project_root / "knowledge" / "etps" / "raw"
        self.index_dir = Path("/app/data/indices")  # Caminho padrão conforme especificação
        
        # Criar diretórios se não existirem
        self.parsed_dir.mkdir(parents=True, exist_ok=True)
        self.raw_pdfs_dir.mkdir(parents=True, exist_ok=True)
        self.index_dir.mkdir(parents=True, exist_ok=True)

    def ingest_pdfs_and_jsonl(self, rebuild: bool = False) -> bool:
        """
        Ingere PDFs da pasta knowledge/etps/raw/ e arquivos JSONL da pasta knowledge/etps/parsed/
        
        Args:
            rebuild: Se True, limpa dados existentes antes da ingestão
            
        Returns:
            bool: True se a ingestão foi bem-sucedida
        """
        try:
            logger.info("Iniciando ingestão de PDFs e arquivos JSONL...")
            
            # Usar sempre o shared db.session do PostgreSQL
            if rebuild:
                logger.info("Modo rebuild: limpando dados existentes...")
                db.session.query(KbChunk).delete()
                db.session.query(KbDocument).delete()
                db.session.commit()
            
            total_chunks = 0
            
            # Processar PDFs primeiro
            pdf_chunks = self._process_pdfs()
            total_chunks += pdf_chunks
            
            # Processar JSONLs existentes
            jsonl_chunks = self._process_jsonl_files()
            total_chunks += jsonl_chunks
            
            db.session.commit()
            logger.info(f"Ingestão concluída: {total_chunks} chunks processados")
            
            # Gerar embeddings e criar índice FAISS
            if self.embeddings_provider == 'openai' and self.openai_client:
                self._generate_embeddings_and_faiss_index()
            
            return True
                
        except Exception as e:
            logger.error(f"Erro na ingestão: {str(e)}")
            db.session.rollback()
            return False

    def _process_pdfs(self) -> int:
        """
        Processa todos os PDFs da pasta knowledge/etps/raw/
        
        Returns:
            int: Número de chunks processados
        """
        try:
            pdf_files = list(self.raw_pdfs_dir.glob("*.pdf"))
            
            if not pdf_files:
                logger.info(f"Nenhum arquivo PDF encontrado em {self.raw_pdfs_dir}")
                return 0
            
            logger.info(f"Encontrados {len(pdf_files)} arquivos PDF")
            total_chunks = 0
            
            for pdf_file in pdf_files:
                try:
                    logger.info(f"Processando PDF: {pdf_file.name}")
                    
                    # Extrair texto do PDF
                    text_content = self._extract_pdf_text(pdf_file)
                    
                    if not text_content.strip():
                        logger.warning(f"PDF {pdf_file.name} está vazio ou não foi possível extrair texto")
                        continue
                    
                    # Criar KnowledgeBaseDocument
                    kb_doc = KnowledgeBaseDocument(
                        id=str(uuid.uuid4()),
                        title=pdf_file.stem,
                        section="requisitos",
                        content=text_content
                    )
                    
                    # Processar e salvar no banco usando db.session
                    chunks_processed = self._process_knowledge_base_document(kb_doc, pdf_file.stem)
                    total_chunks += chunks_processed
                    
                except Exception as e:
                    logger.error(f"Erro processando PDF {pdf_file.name}: {e}")
                    continue
            
            return total_chunks
            
        except Exception as e:
            logger.error(f"Erro processando PDFs: {e}")
            return 0

    def _extract_pdf_text(self, pdf_path: Path) -> str:
        """
        Extrai texto completo de um arquivo PDF
        
        Args:
            pdf_path: Caminho para o arquivo PDF
            
        Returns:
            str: Texto extraído do PDF
        """
        try:
            text_content = ""
            
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text.strip():
                            text_content += f"\n--- Página {page_num + 1} ---\n"
                            text_content += page_text + "\n"
                    except Exception as e:
                        logger.warning(f"Erro extraindo texto da página {page_num + 1} do PDF {pdf_path.name}: {e}")
                        continue
            
            return text_content.strip()
            
        except Exception as e:
            logger.error(f"Erro extraindo texto do PDF {pdf_path}: {e}")
            return ""

    def _process_knowledge_base_document(self, kb_doc: KnowledgeBaseDocument, filename: str) -> int:
        """
        Processa um KnowledgeBaseDocument e cria chunks na base de dados usando db.session
        
        Args:
            kb_doc: Documento da base de conhecimento
            filename: Nome do arquivo
            
        Returns:
            int: Número de chunks processados
        """
        try:
            # Verificar se o documento já existe
            existing_doc = db.session.query(KbDocument).filter_by(
                filename=filename,
                objective_slug=kb_doc.section
            ).first()
            
            if existing_doc:
                logger.info(f"Documento {filename} já existe, atualizando...")
                # Remover chunks existentes
                db.session.query(KbChunk).filter_by(kb_document_id=existing_doc.id).delete()
                document = existing_doc
            else:
                # Criar novo documento
                document = KbDocument(
                    filename=filename,
                    objective_slug=kb_doc.section
                )
                db.session.add(document)
                db.session.flush()  # Para obter o ID
            
            # Dividir conteúdo em chunks
            chunks = self._split_content(kb_doc.content, max_chars=2000)
            chunks_processed = 0
            
            for chunk_index, chunk_content in enumerate(chunks):
                kb_chunk = KbChunk(
                    kb_document_id=document.id,
                    section_type=kb_doc.section,
                    content_text=chunk_content.strip(),
                    objective_slug=kb_doc.section
                )
                db.session.add(kb_chunk)
                chunks_processed += 1
            
            logger.info(f"Documento {filename}: {chunks_processed} chunks criados")
            return chunks_processed
            
        except Exception as e:
            logger.error(f"Erro processando documento {filename}: {str(e)}")
            return 0

    def _process_jsonl_files(self) -> int:
        """
        Processa arquivos JSONL da pasta knowledge/etps/parsed/ usando db.session
        
        Returns:
            int: Número de chunks processados
        """
        try:
            jsonl_files = list(self.parsed_dir.glob("*.jsonl"))
            
            if not jsonl_files:
                logger.info(f"Nenhum arquivo JSONL encontrado em {self.parsed_dir}")
                return 0
            
            logger.info(f"Encontrados {len(jsonl_files)} arquivos JSONL")
            total_chunks = 0
            total_documents = 0
            
            for jsonl_file in jsonl_files:
                logger.info(f"Processando arquivo JSONL: {jsonl_file.name}")
                file_documents = 0
                file_chunks = 0
                
                # Ler e processar cada linha do JSONL
                with open(jsonl_file, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        try:
                            if not line.strip():
                                continue
                                
                            data = json.loads(line)
                            chunks_processed = self._process_etp_document(data, jsonl_file.stem)
                            if chunks_processed > 0:
                                file_documents += 1
                                total_documents += 1
                            file_chunks += chunks_processed
                            total_chunks += chunks_processed
                            
                        except json.JSONDecodeError as e:
                            logger.error(f"Erro JSON na linha {line_num} de {jsonl_file.name}: {e}")
                            continue
                        except Exception as e:
                            logger.error(f"Erro processando linha {line_num} de {jsonl_file.name}: {e}")
                            continue
                
                logger.info(f"Arquivo {jsonl_file.name}: {file_documents} documentos, {file_chunks} chunks processados")
            
            logger.info(f"TOTAL: {total_documents} documentos, {total_chunks} chunks processados com sucesso")
            return total_chunks
            
        except Exception as e:
            logger.error(f"Erro processando JSONLs: {e}")
            return 0

    def ingest_jsonl_files(self, rebuild: bool = False) -> bool:
        """
        Ingere arquivos JSONL da pasta knowledge/etps/parsed/
        
        Args:
            rebuild: Se True, limpa dados existentes antes da ingestão
            
        Returns:
            bool: True se a ingestão foi bem-sucedida
        """
        try:
            logger.info("Iniciando ingestão de arquivos JSONL...")
            
            # Verificar se existem arquivos JSONL
            jsonl_files = list(self.parsed_dir.glob("*.jsonl"))
            
            if not jsonl_files:
                logger.warning(f"Nenhum arquivo JSONL encontrado em {self.parsed_dir}")
                logger.info("Para testar, crie um arquivo de exemplo...")
                self._create_sample_data()
                jsonl_files = list(self.parsed_dir.glob("*.jsonl"))
            
            logger.info(f"Encontrados {len(jsonl_files)} arquivos JSONL")
            
            # Usar db.session diretamente
            if rebuild:
                logger.info("Modo rebuild: limpando dados existentes...")
                db.session.query(KbChunk).delete()
                db.session.query(KbDocument).delete()
                db.session.commit()
                
                total_chunks = 0
                total_documents = 0
                
                for jsonl_file in jsonl_files:
                    logger.info(f"Processando arquivo: {jsonl_file.name}")
                    file_documents = 0
                    file_chunks = 0
                    
                    # Ler e processar cada linha do JSONL
                    with open(jsonl_file, 'r', encoding='utf-8') as f:
                        for line_num, line in enumerate(f, 1):
                            try:
                                if not line.strip():
                                    continue
                                    
                                data = json.loads(line)
                                chunks_processed = self._process_etp_document(data, jsonl_file.stem)
                                if chunks_processed > 0:
                                    file_documents += 1
                                    total_documents += 1
                                file_chunks += chunks_processed
                                total_chunks += chunks_processed
                                
                            except json.JSONDecodeError as e:
                                logger.error(f"Erro JSON na linha {line_num} de {jsonl_file.name}: {e}")
                                continue
                            except Exception as e:
                                logger.error(f"Erro processando linha {line_num} de {jsonl_file.name}: {e}")
                                continue
                    
                    logger.info(f"Arquivo {jsonl_file.name}: {file_documents} documentos, {file_chunks} chunks processados")
                
            db.session.commit()
            logger.info(f"Ingestão concluída: {total_documents} documentos, {total_chunks} chunks processados com sucesso")
            
            # Gerar embeddings e criar índice FAISS
            if self.embeddings_provider == 'openai' and self.openai_client:
                self._generate_embeddings_and_faiss_index()
            
            return True
                
        except Exception as e:
            logger.error(f"Erro na ingestão: {str(e)}")
            return False

    def _process_etp_document(self, data: Dict, filename: str) -> int:
        """
        Processa um documento ETP e cria chunks na base de dados usando db.session
        
        Args:
            data: Dados do documento JSON
            filename: Nome do arquivo
            
        Returns:
            int: Número de chunks processados
        """
        try:
            # Extrair metadados do documento
            objective_slug = data.get('objective_slug', filename)
            
            # Verificar se o documento já existe
            existing_doc = db.session.query(KbDocument).filter_by(
                filename=filename,
                objective_slug=objective_slug
            ).first()
            
            if existing_doc:
                logger.info(f"Documento {filename} já existe, atualizando...")
                # Remover chunks existentes
                db.session.query(KbChunk).filter_by(kb_document_id=existing_doc.id).delete()
                kb_document = existing_doc
            else:
                # Criar novo documento - KbDocument só aceita filename, etp_id e objective_slug
                kb_document = KbDocument(
                    filename=filename,
                    objective_slug=objective_slug
                )
                db.session.add(kb_document)
                db.session.flush()  # Para obter o ID
            
            chunks_processed = 0
            
            # Caso 1: Estrutura atual com sections (formato complexo)
            if 'sections' in data:
                sections = data.get('sections', [])
                
                for section in sections:
                    section_type = section.get('type', 'unknown')
                    content = section.get('content', '')
                    
                    if not content.strip():
                        continue
                    
                    # Dividir conteúdo em chunks menores se necessário
                    chunks = self._split_content(content, max_chars=2000)
                    
                    for chunk_index, chunk_content in enumerate(chunks):
                        kb_chunk = KbChunk(
                            kb_document_id=kb_document.id,
                            section_type=section_type,
                            content_text=chunk_content.strip(),
                            objective_slug=objective_slug
                        )
                        db.session.add(kb_chunk)
                        
                    chunks_processed += len(chunks)
            
            # Caso 2: Estrutura simples descrita na issue (need, requirements, etc.)
            else:
                # Processar campos individuais como seções separadas
                field_mappings = {
                    'need': 'Necessidade',
                    'requirements': 'Requisitos', 
                    'legal_framework': 'Marco Legal',
                    'technical_specifications': 'Especificações Técnicas',
                    'evaluation_criteria': 'Critérios de Avaliação'
                }
                
                for field_key, section_name in field_mappings.items():
                    if field_key in data and data[field_key]:
                        content = str(data[field_key]).strip()
                        if content:
                            # Dividir conteúdo em chunks se necessário
                            chunks = self._split_content(content, max_chars=2000)
                            
                            for chunk_content in chunks:
                                kb_chunk = KbChunk(
                                    kb_document_id=kb_document.id,
                                    section_type=section_name.lower().replace(' ', '_'),
                                    content_text=chunk_content.strip(),
                                    objective_slug=objective_slug
                                )
                                db.session.add(kb_chunk)
                                
                            chunks_processed += len(chunks)
            
            logger.info(f"Documento {filename}: {chunks_processed} chunks criados")
            return chunks_processed
            
        except Exception as e:
            logger.error(f"Erro processando documento {filename}: {str(e)}")
            return 0

    def _split_content(self, content: str, max_chars: int = 2000) -> List[str]:
        """
        Divide conteúdo em chunks menores
        
        Args:
            content: Conteúdo a ser dividido
            max_chars: Número máximo de caracteres por chunk
            
        Returns:
            Lista de chunks
        """
        if len(content) <= max_chars:
            return [content]
        
        chunks = []
        sentences = content.split('.')
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # Adicionar ponto final se não houver
            if not sentence.endswith('.'):
                sentence += '.'
            
            # Verificar se adicionar a sentença excede o limite
            if len(current_chunk) + len(sentence) + 1 > max_chars:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = sentence
                else:
                    # Sentença muito longa, dividir por caracteres
                    chunks.append(sentence[:max_chars])
                    current_chunk = sentence[max_chars:]
            else:
                current_chunk += " " + sentence if current_chunk else sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks

    def _generate_embeddings_and_faiss_index(self) -> None:
        """Gera embeddings e cria índice FAISS usando db.session"""
        try:
            logger.info("Gerando embeddings e criando índice FAISS...")
            
            # Buscar todos os chunks usando db.session
            chunks = db.session.query(KbChunk).all()
            
            if not chunks:
                logger.warning("Nenhum chunk encontrado para gerar embeddings")
                return
            
            logger.info(f"Processando {len(chunks)} chunks para geração de embeddings...")
            
            embeddings_list = []
            chunk_ids = []
            chunks_with_content = 0
            chunks_with_embeddings = 0
            
            for chunk in chunks:
                # Verificar se o chunk tem conteúdo válido
                if chunk.content and chunk.content.strip():
                    chunks_with_content += 1
                    logger.debug(f"Chunk {chunk.id}: content extraído ({len(chunk.content)} caracteres)")
                    
                    # Gerar embedding
                    embedding = self._get_embedding(chunk.content)
                    if embedding:
                        embeddings_list.append(np.array(embedding, dtype=np.float32))
                        chunk_ids.append(chunk.id)
                        chunks_with_embeddings += 1
                        
                        # Salvar embedding no banco
                        chunk.embedding = json.dumps(embedding)
                        logger.debug(f"Chunk {chunk.id}: embedding gerado com sucesso")
                    else:
                        logger.warning(f"Chunk {chunk.id}: falha ao gerar embedding")
                else:
                    logger.warning(f"Chunk {chunk.id}: conteúdo vazio ou inválido")
            
            logger.info(f"RESUMO DE PROCESSAMENTO:")
            logger.info(f"- Total de chunks processados: {len(chunks)}")
            logger.info(f"- Chunks com conteúdo válido: {chunks_with_content}")
            logger.info(f"- Chunks com embeddings gerados: {chunks_with_embeddings}")
            logger.info(f"- Taxa de sucesso: {chunks_with_embeddings/len(chunks)*100:.1f}%" if chunks else "0%")
            
            db.session.commit()
            
            if embeddings_list:
                # Criar índice FAISS
                embeddings_matrix = np.vstack(embeddings_list)
                dimension = embeddings_matrix.shape[1]
                
                # Normalizar para cosine similarity
                faiss.normalize_L2(embeddings_matrix)
                
                # Criar índice
                index = faiss.IndexFlatIP(dimension)
                index.add(embeddings_matrix)
                
                # Salvar índice FAISS conforme especificação
                index_path = self.index_dir / "faiss.index"
                faiss.write_index(index, str(index_path))
                
                # Salvar mapeamento de IDs para FAISS
                mapping_path = self.index_dir / "faiss_mapping.json"
                with open(mapping_path, 'w') as f:
                    json.dump(chunk_ids, f)
                
                # Criar e salvar índice BM25 conforme especificação
                self._create_bm25_index(chunks)
                
                logger.info(f"Índice FAISS criado: {len(embeddings_list)} vetores, dimensão {dimension}")
                logger.info(f"Salvo em: {index_path}")
                
        except Exception as e:
            logger.error(f"Erro gerando embeddings/FAISS: {str(e)}")

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Gera embedding usando OpenAI API"""
        if not self.openai_client:
            return None
        
        try:
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text.replace("\n", " ")
            )
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"Erro ao gerar embedding: {str(e)}")
            return None

    def _create_sample_data(self) -> None:
        """Cria dados de exemplo para teste"""
        logger.info("Criando dados de exemplo...")
        
        sample_data = [
            {
                "objective_slug": "manutencao_computadores",
                "title": "ETP - Manutenção de Computadores",
                "type": "etp",
                "metadata": {"version": "1.0", "created_by": "system"},
                "sections": [
                    {
                        "type": "requisito",
                        "title": "Objetivo da Contratação",
                        "content": "O objetivo da contratação é a manutenção preventiva e corretiva de equipamentos de informática, incluindo computadores desktop, notebooks e impressoras. Os serviços devem garantir o perfeito funcionamento dos equipamentos, com atendimento em até 24 horas para chamados urgentes.",
                        "page": 1
                    },
                    {
                        "type": "requisito",
                        "title": "Especificações Técnicas",
                        "content": "A manutenção deve incluir limpeza interna dos equipamentos, substituição de peças defeituosas, atualização de drivers, verificação de funcionamento de todos os componentes e testes de performance. As peças utilizadas devem ser originais ou compatíveis de qualidade equivalente.",
                        "page": 2
                    },
                    {
                        "type": "norma_legal",
                        "title": "Lei de Licitações",
                        "content": "A contratação deve seguir os preceitos da Lei 14.133/2021 (Nova Lei de Licitações), especialmente quanto aos critérios de julgamento técnico e preço. É necessário comprovação de capacidade técnica da empresa contratada através de atestados de capacidade técnica.",
                        "page": 3
                    }
                ]
            },
            {
                "objective_slug": "servicos_limpeza",
                "title": "ETP - Serviços de Limpeza",
                "type": "etp",
                "metadata": {"version": "1.0", "created_by": "system"},
                "sections": [
                    {
                        "type": "requisito",
                        "title": "Escopo dos Serviços",
                        "content": "Os serviços de limpeza incluem limpeza geral das dependências do órgão, incluindo salas, corredores, banheiros, copa e áreas externas. A frequência deve ser diária para áreas de maior movimento e semanal para áreas administrativas.",
                        "page": 1
                    },
                    {
                        "type": "norma_legal",
                        "title": "Normas de Segurança do Trabalho",
                        "content": "Os serviços devem ser executados em conformidade com as Normas Regulamentadoras do Ministério do Trabalho, especialmente NR-6 (EPI) e NR-32 (Segurança em Serviços de Saúde). Todos os funcionários devem utilizar equipamentos de proteção individual adequados.",
                        "page": 2
                    }
                ]
            }
        ]
        
        # Criar arquivo de exemplo
        sample_file = self.parsed_dir / "sample_etps.jsonl"
        with open(sample_file, 'w', encoding='utf-8') as f:
            for data in sample_data:
                f.write(json.dumps(data, ensure_ascii=False) + '\n')
        
        logger.info(f"Arquivo de exemplo criado: {sample_file}")

    def ingest_initial_docs(self) -> bool:
        """
        Função clara para ingestão inicial de documentos.
        Deve ser chamada pelo FlaskConfig no startup da aplicação.
        
        Returns:
            bool: True se a ingestão foi bem-sucedida
        """
        try:
            logger.info("Executando ingestão inicial de documentos...")
            
            # Configurar cliente OpenAI se disponível
            openai_client = None
            if os.getenv('OPENAI_API_KEY') and os.getenv('OPENAI_API_KEY') != 'test_key':
                try:
                    import openai
                    openai_client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
                    logger.info("Cliente OpenAI configurado para ingestão inicial")
                except ImportError:
                    logger.warning("Biblioteca openai não encontrada para ingestão inicial")
            
            # Atualizar cliente OpenAI na instância
            if openai_client:
                self.openai_client = openai_client
            
            # Executar ingestão inicial (rebuild=True para garantir dados atualizados)
            return self.ingest_pdfs_and_jsonl(rebuild=True)
            
        except Exception as e:
            logger.error(f"Erro na ingestão inicial: {str(e)}")
            return False


def main():
    """Função principal do CLI"""
    parser = argparse.ArgumentParser(description="Ingestor de ETPs para base de conhecimento RAG")
    parser.add_argument("--rebuild", action="store_true", help="Limpar dados existentes antes da ingestão")
    parser.add_argument("--database-url", help="URL do banco de dados")
    
    args = parser.parse_args()
    
    try:
        # Configurar cliente OpenAI se disponível
        openai_client = None
        if os.getenv('OPENAI_API_KEY') and os.getenv('OPENAI_API_KEY') != 'test_key':
            try:
                import openai
                openai_client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
                logger.info("Cliente OpenAI configurado")
            except ImportError:
                logger.warning("Biblioteca openai não encontrada")
        
        # Executar ingestão (ETPIngestor cria suas próprias tabelas)
        ingestor = ETPIngestor(args.database_url, openai_client)
        success = ingestor.ingest_pdfs_and_jsonl(rebuild=args.rebuild)
        
        if success:
            logger.info("✅ Ingestão concluída com sucesso!")
            print("\n" + "="*50)
            print("🎉 INGESTÃO CONCLUÍDA COM SUCESSO!")
            print("="*50)
            print("\nPróximos passos:")
            print("1. Iniciar a aplicação: python src/main/python/applicationApi.py")
            print("2. Testar a busca usando as funções do módulo retrieval")
            print("\nExemplo de teste:")
            print('retrieval.search_requirements("manutencao_computadores", "objetivo manutencao de pcs")')
            sys.exit(0)
        else:
            logger.error("❌ Falha na ingestão")
            sys.exit(1)
                
    except KeyboardInterrupt:
        logger.info("Ingestão cancelada pelo usuário")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Erro na execução: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()


    def _create_bm25_index(self, chunks: List[Dict]):
        """
        Cria um índice BM25 a partir dos chunks e o salva em disco.
        """
        try:
            from rank_bm25 import BM25Okapi
            import pickle

            logger.info("Criando índice BM25...")
            
            # Extrai o conteúdo de texto dos chunks
            documents = [chunk.content_text for chunk in chunks]
            tokenized_documents = [doc.split(" ") for doc in documents]
            
            # Cria o índice BM25
            bm25 = BM25Okapi(tokenized_documents)
            
            # Salva o índice em disco
            index_path = self.index_dir / "bm25_index.pkl"
            with open(index_path, 'wb') as f:
                pickle.dump(bm25, f)
            
            logger.info(f"Índice BM25 criado e salvo em {index_path}")
            
        except Exception as e:
            logger.error(f"Erro ao criar índice BM25: {e}")

