"""
Módulo de recuperação (retrieval) para o sistema RAG.
Implementa busca híbrida usando BM25 e FAISS para consultas em requisitos e normas legais.
"""

import os
import json
import pickle
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import numpy as np
from rank_bm25 import BM25Okapi
from rapidfuzz import fuzz
from domain.interfaces.dataprovider.DatabaseConfig import db

# Import opcional de FAISS (fallback para BM25 se não disponível)
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    logging.warning("⚠️  FAISS não disponível - usando apenas BM25")

# Configurar logging
logger = logging.getLogger(__name__)

class RAGRetrieval:
    """Classe principal para recuperação de informações usando RAG"""
    
    def __init__(self, db_session=None, index_type="faiss", embeddings_provider="openai", openai_client=None):
        # Support both old and new calling patterns
        if isinstance(db_session, type(openai_client)) and db_session is not None:
            # Old pattern: RAGRetrieval(database_url, openai_client)
            self.openai_client = index_type if index_type else openai_client
            self.db_session = db.session
        elif openai_client is not None:
            # New pattern: RAGRetrieval(openai_client=client)
            self.openai_client = openai_client
            self.db_session = db_session or db.session
        else:
            # Fallback: RAGRetrieval(db_session, index_type, embeddings_provider)
            self.openai_client = openai_client
            self.db_session = db_session or db.session
            
        self.index_type = index_type if isinstance(index_type, str) else "faiss"
        self.embeddings_provider = embeddings_provider if isinstance(embeddings_provider, str) else os.getenv('EMBEDDINGS_PROVIDER', 'openai')
        
        # Configurar diretórios para índices
        self.project_root = Path(__file__).parent.parent.parent.parent.parent
        self.index_dir = self.project_root / "src" / "main" / "python" / "rag" / "index"
        self.bm25_dir = self.index_dir / "bm25"
        
        # Criar diretórios se não existirem
        self.bm25_dir.mkdir(parents=True, exist_ok=True)
        
        # Índices BM25 por section_type
        self.bm25_indices = {}
        self.bm25_documents = {}  # Mapear documentos para índices BM25
        
        # Índice FAISS
        self.faiss_index = None
        self.faiss_documents = []  # Lista de documentos correspondentes aos vetores FAISS
        
        # Cache de embeddings
        self.embedding_cache = {}
        
        # Tentar carregar índices BM25 existentes
        self._load_bm25_indices()

    def build_indices(self) -> bool:
        """
        Constrói os índices BM25 e FAISS a partir dos dados do banco.
        
        Returns:
            bool: True se os índices foram construídos com sucesso
        """
        try:
            logger.info("Iniciando construção dos índices RAG...")
            
            # Importar modelos aqui para evitar import circular
            from domain.dto.KbDto import KbChunk
            
            # Buscar todos os chunks da base de conhecimento
            chunks = KbChunk.query.all()
            
            if not chunks:
                logger.warning("Nenhum chunk encontrado na base de conhecimento")
                return False
            
            logger.info(f"Encontrados {len(chunks)} chunks para indexação")
            
            # Agrupar chunks por section_type para BM25
            chunks_by_type = {}
            for chunk in chunks:
                if chunk.section_type not in chunks_by_type:
                    chunks_by_type[chunk.section_type] = []
                chunks_by_type[chunk.section_type].append(chunk)
            
            # Construir índices BM25 por section_type
            for section_type, type_chunks in chunks_by_type.items():
                logger.info(f"Construindo índice BM25 para {section_type}: {len(type_chunks)} chunks")
                
                # Tokenizar documentos para BM25
                tokenized_docs = []
                doc_mapping = []
                
                for chunk in type_chunks:
                    tokens = self._tokenize(chunk.content)
                    tokenized_docs.append(tokens)
                    doc_mapping.append({
                        'chunk_id': chunk.id,
                        'document_id': chunk.kb_document_id,
                        'content': chunk.content,
                        'section_title': chunk.section_type,
                        'objective_slug': getattr(chunk.kb_document, 'objective_slug', ''),
                        'chunk': chunk
                    })
                
                # Criar índice BM25
                if tokenized_docs:
                    bm25 = BM25Okapi(tokenized_docs)
                    self.bm25_indices[section_type] = bm25
                    self.bm25_documents[section_type] = doc_mapping
            
            # Construir índice FAISS se provider for OpenAI
            if self.embeddings_provider == 'openai' and self.openai_client:
                logger.info("Construindo índice FAISS com embeddings OpenAI...")
                try:
                    self._build_faiss_index(chunks)
                    logger.info("✅ Índice FAISS construído com sucesso")
                except Exception as e:
                    logger.warning(f"⚠️  Falha ao construir índice FAISS: {e}")
                    logger.info("Sistema continuará funcionando com BM25 apenas")
            else:
                logger.info("⚠️  FAISS não será construído (provider não é OpenAI ou client ausente)")
                logger.info("Sistema funcionará com BM25 apenas")
            
            # Resumo final
            bm25_types = list(self.bm25_indices.keys())
            faiss_status = "disponível" if self.faiss_index is not None else "não disponível"
            logger.info(f"✅ Índices RAG construídos: BM25 ({len(bm25_types)} tipos), FAISS ({faiss_status})")
            
            # Salvar índices BM25 para uso futuro
            self._save_bm25_indices()
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao construir índices: {str(e)}")
            return False

    def _build_faiss_index(self, chunks: List) -> None:
        """Constrói o índice FAISS com embeddings"""
        if not FAISS_AVAILABLE:
            logger.warning("FAISS não disponível - pulando construção de índice FAISS")
            return
        
        embeddings_list = []
        documents_list = []
        chunks_with_embeddings = 0
        chunks_without_embeddings = 0
        
        logger.info(f"Processando {len(chunks)} chunks para construção do índice FAISS...")
        
        for chunk in chunks:
            # Tentar usar embedding já salvo
            if chunk.embedding:
                try:
                    # Handle both JSON/text and ARRAY(Float) formats
                    if isinstance(chunk.embedding, str):
                        # JSON format - parse the string
                        embedding = json.loads(chunk.embedding)
                    elif isinstance(chunk.embedding, list):
                        # Direct list format
                        embedding = chunk.embedding
                    else:
                        # ARRAY(Float) format - convert to list
                        embedding = list(chunk.embedding)
                    
                    if embedding and len(embedding) > 0:
                        embeddings_list.append(np.array(embedding, dtype=np.float32))
                        documents_list.append({
                            'chunk_id': chunk.id,
                            'document_id': chunk.kb_document_id,
                            'content': chunk.content,
                            'section_type': chunk.section_type,
                            'section_title': chunk.section_type,
                            'objective_slug': getattr(chunk.kb_document, 'objective_slug', ''),
                            'chunk': chunk
                        })
                        chunks_with_embeddings += 1
                    else:
                        logger.warning(f"Embedding vazio para chunk {chunk.id}")
                        chunks_without_embeddings += 1
                        
                except (json.JSONDecodeError, ValueError, TypeError) as e:
                    logger.warning(f"Embedding inválido para chunk {chunk.id}: {str(e)}")
                    chunks_without_embeddings += 1
                    continue
            else:
                chunks_without_embeddings += 1
                # Gerar embedding usando OpenAI
                embedding = self._get_embedding(chunk.content)
                if embedding is not None:
                    embeddings_list.append(np.array(embedding, dtype=np.float32))
                    documents_list.append({
                        'chunk_id': chunk.id,
                        'document_id': chunk.kb_document_id,
                        'content': chunk.content,
                        'section_type': chunk.section_type,
                        'section_title': chunk.section_type,
                        'objective_slug': getattr(chunk.kb_document, 'objective_slug', ''),
                        'chunk': chunk
                    })
        
        logger.info(f"Embeddings encontrados: {chunks_with_embeddings}, Sem embeddings: {chunks_without_embeddings}")
        
        if embeddings_list:
            # Criar índice FAISS
            embeddings_matrix = np.vstack(embeddings_list)
            dimension = embeddings_matrix.shape[1]
            
            # Normalize vectors before adding to FAISS index
            faiss.normalize_L2(embeddings_matrix)
            
            self.faiss_index = faiss.IndexFlatIP(dimension)  # Inner Product para similaridade
            self.faiss_index.add(embeddings_matrix)
            self.faiss_documents = documents_list
            
            logger.info(f"Índice FAISS criado com {len(embeddings_list)} vetores de dimensão {dimension}")
        else:
            logger.warning("Nenhum embedding válido encontrado - índice FAISS não será criado")

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Gera embedding usando OpenAI API"""
        if not self.openai_client:
            return None
            
        # Verificar cache
        text_hash = str(hash(text))
        if text_hash in self.embedding_cache:
            return self.embedding_cache[text_hash]
        
        try:
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text.replace("\n", " ")
            )
            embedding = response.data[0].embedding
            
            # Salvar no cache
            self.embedding_cache[text_hash] = embedding
            return embedding
            
        except Exception as e:
            logger.error(f"Erro ao gerar embedding: {str(e)}")
            return None

    def _tokenize(self, text: str) -> List[str]:
        """Tokeniza texto para BM25"""
        import re
        # Tokenização simples: lowercase, remover pontuação, dividir por espaços
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        tokens = text.split()
        return [token for token in tokens if len(token) > 2]

    def search_requirements(self, objective_slug: str, query: str, k: int = 5) -> List[Dict]:
        """
        Busca requisitos usando busca híbrida (BM25 + FAISS).
        
        Args:
            objective_slug: Slug do objetivo para filtrar resultados
            query: Query de busca
            k: Número máximo de resultados
            
        Returns:
            Lista de trechos com score híbrido
        """
        return self._hybrid_search('requisito', objective_slug, query, k)

    def search_legal(self, objective_slug: str, query: str, k: int = 8) -> List[Dict]:
        """
        Busca normas legais usando busca híbrida (BM25 + FAISS).
        
        Args:
            objective_slug: Slug do objetivo para filtrar resultados
            query: Query de busca
            k: Número máximo de resultados
            
        Returns:
            Lista de trechos com score híbrido
        """
        return self._hybrid_search('norma_legal', objective_slug, query, k)

    def _hybrid_search(self, section_type: str, objective_slug: str, query: str, k: int) -> List[Dict]:
        """
        Implementa busca híbrida combinando BM25 e FAISS.
        
        Fallback robusto:
        - Se FAISS não disponível → usa apenas BM25
        - Se BM25 não disponível → tenta reconstruir ou retorna vazio
        - Se ambos disponíveis → combina com pesos (70% BM25 + 30% FAISS)
        
        Args:
            section_type: Tipo de seção ('requisito', 'norma_legal', etc.)
            objective_slug: Slug do objetivo
            query: Query de busca
            k: Número de resultados
            
        Returns:
            Lista de resultados ordenados por score híbrido
        """
        results = []
        
        try:
            # Busca BM25 (sempre tentada primeiro)
            bm25_results = self._search_bm25(section_type, objective_slug, query, k * 2)
            
            # Busca FAISS (opcional, fallback para BM25 se não disponível)
            faiss_results = []
            faiss_available = False
            
            if self.faiss_index is not None:
                try:
                    faiss_results = self._search_faiss(section_type, objective_slug, query, k * 2)
                    faiss_available = True
                except Exception as e:
                    logger.warning(f"FAISS search failed, falling back to BM25 only: {e}")
                    faiss_available = False
            else:
                logger.debug("FAISS index not available, using BM25 only")
            
            # Se não há resultados BM25 e não há FAISS, retornar vazio
            if not bm25_results and not faiss_results:
                logger.warning(f"No results found for section_type={section_type}, query={query[:50]}")
                return []
            
            # FALLBACK: Se apenas BM25 disponível, retornar resultados BM25 puros
            if bm25_results and not faiss_available:
                logger.debug(f"Using BM25-only mode (FAISS unavailable)")
                for result in bm25_results[:k]:
                    result['hybrid_score'] = result['score']  # BM25 score como híbrido
                    result['search_mode'] = 'bm25_only'
                return bm25_results[:k]
            
            # FALLBACK: Se apenas FAISS disponível (raro), retornar resultados FAISS puros
            if faiss_results and not bm25_results:
                logger.debug(f"Using FAISS-only mode (BM25 unavailable)")
                for result in faiss_results[:k]:
                    result['hybrid_score'] = result['score']  # FAISS score como híbrido
                    result['search_mode'] = 'faiss_only'
                return faiss_results[:k]
            
            # MODO HÍBRIDO: Combinar resultados BM25 e FAISS
            all_results = {}
            
            # Adicionar resultados BM25
            for result in bm25_results:
                chunk_id = result['chunk_id']
                all_results[chunk_id] = {
                    **result,
                    'bm25_score': result['score'],
                    'faiss_score': 0.0
                }
            
            # Adicionar/combinar resultados FAISS
            for result in faiss_results:
                chunk_id = result['chunk_id']
                if chunk_id in all_results:
                    all_results[chunk_id]['faiss_score'] = result['score']
                else:
                    all_results[chunk_id] = {
                        **result,
                        'bm25_score': 0.0,
                        'faiss_score': result['score']
                    }
            
            # Calcular score híbrido e ordenar
            for chunk_id, result in all_results.items():
                # Score híbrido: 70% BM25 + 30% FAISS
                hybrid_score = (0.7 * result['bm25_score']) + (0.3 * result['faiss_score'])
                result['hybrid_score'] = hybrid_score
                result['search_mode'] = 'hybrid'  # Indicar modo híbrido
                results.append(result)
            
            # Ordenar por score híbrido
            results.sort(key=lambda x: x['hybrid_score'], reverse=True)
            
            # Retornar top-k resultados
            return results[:k]
            
        except Exception as e:
            logger.error(f"Erro na busca híbrida: {str(e)}")
            return []

    def _search_bm25(self, section_type: str, objective_slug: str, query: str, k: int) -> List[Dict]:
        """Busca usando BM25"""
        if section_type not in self.bm25_indices:
            logger.warning(f"Índice BM25 não encontrado para {section_type}")
            logger.info("[RAG] Tentando reconstruir índices automaticamente...")
            
            # Tentar reconstruir índices automaticamente
            if self.build_indices():
                logger.info("[RAG] Índices reconstruídos com sucesso")
                # Verificar novamente se o índice existe após reconstrução
                if section_type not in self.bm25_indices:
                    logger.error(f"Falha ao reconstruir índice BM25 para {section_type}")
                    return []
            else:
                logger.error("Falha ao reconstruir índices BM25")
                return []
        
        bm25 = self.bm25_indices[section_type]
        documents = self.bm25_documents[section_type]
        
        # Tokenizar query
        query_tokens = self._tokenize(query)
        
        # Buscar com BM25
        scores = bm25.get_scores(query_tokens)
        
        # Criar lista de resultados
        results = []
        for i, score in enumerate(scores):
            doc = documents[i]
            
            # Filtrar por objective_slug se especificado
            if objective_slug and doc['objective_slug'] != objective_slug:
                continue
                
            results.append({
                'chunk_id': doc['chunk_id'],
                'document_id': doc['document_id'],
                'content': doc['content'],
                'section_title': doc['section_title'],
                'section_type': section_type,
                'objective_slug': doc['objective_slug'],
                'score': float(score),
                'source': 'bm25'
            })
        
        # Ordenar por score e retornar top-k
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:k]

    def _search_faiss(self, section_type: str, objective_slug: str, query: str, k: int) -> List[Dict]:
        """Busca usando FAISS"""
        if self.faiss_index is None:
            logger.warning("Índice FAISS não disponível")
            return []
        
        # Gerar embedding da query
        query_embedding = self._get_embedding(query)
        if query_embedding is None:
            logger.warning("Não foi possível gerar embedding para a query")
            return []
        
        # Buscar no FAISS
        query_vector = np.array([query_embedding], dtype=np.float32)
        faiss.normalize_L2(query_vector)
        
        scores, indices = self.faiss_index.search(query_vector, min(k * 2, len(self.faiss_documents)))
        
        # Criar lista de resultados
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:  # Índice inválido
                continue
                
            doc = self.faiss_documents[idx]
            
            # Filtrar por section_type e objective_slug
            if doc['section_type'] != section_type:
                continue
                
            if objective_slug and doc['objective_slug'] != objective_slug:
                continue
            
            results.append({
                'chunk_id': doc['chunk_id'],
                'document_id': doc['document_id'],
                'content': doc['content'],
                'section_title': doc['section_title'],
                'section_type': section_type,
                'objective_slug': doc['objective_slug'],
                'score': float(score),
                'source': 'faiss'
            })
        
        return results[:k]

    def _load_bm25_indices(self) -> None:
        """Carrega índices BM25 existentes do disco"""
        try:
            indices_file = self.bm25_dir / "bm25_indices.pkl"
            documents_file = self.bm25_dir / "bm25_documents.pkl"
            
            if indices_file.exists() and documents_file.exists():
                logger.info("[RAG] Carregando índices BM25 existentes...")
                
                with open(indices_file, 'rb') as f:
                    self.bm25_indices = pickle.load(f)
                    
                with open(documents_file, 'rb') as f:
                    self.bm25_documents = pickle.load(f)
                
                logger.info(f"[RAG] Índice BM25 carregado com sucesso - {len(self.bm25_indices)} seções")
            else:
                logger.info("[RAG] Índice BM25 não encontrado, reconstruindo...")
                
        except Exception as e:
            logger.error(f"Erro ao carregar índices BM25: {e}")
            logger.info("[RAG] Índice BM25 não encontrado, reconstruindo...")
            self.bm25_indices = {}
            self.bm25_documents = {}

    def _save_bm25_indices(self) -> None:
        """Salva índices BM25 no disco"""
        try:
            if not self.bm25_indices:
                logger.warning("Nenhum índice BM25 para salvar")
                return
                
            indices_file = self.bm25_dir / "bm25_indices.pkl"
            documents_file = self.bm25_dir / "bm25_documents.pkl"
            
            with open(indices_file, 'wb') as f:
                pickle.dump(self.bm25_indices, f)
                
            with open(documents_file, 'wb') as f:
                pickle.dump(self.bm25_documents, f)
                
            logger.info(f"[RAG] Índices BM25 salvos com sucesso - {len(self.bm25_indices)} seções")
            
        except Exception as e:
            logger.error(f"Erro ao salvar índices BM25: {e}")


# Instância global do retrieval
_retrieval_instance = None

def get_retrieval_instance(database_url: str = None, openai_client = None) -> RAGRetrieval:
    """Retorna instância singleton do RAGRetrieval"""
    global _retrieval_instance
    
    if _retrieval_instance is None:
        _retrieval_instance = RAGRetrieval(database_url, openai_client)
    
    return _retrieval_instance

def build_indices() -> bool:
    """Função de conveniência para construir índices"""
    retrieval = get_retrieval_instance()
    return retrieval.build_indices()

def search_requirements(objective_slug: str, query: str, k: int = 5) -> List[Dict]:
    """Função de conveniência para busca de requisitos"""
    retrieval = get_retrieval_instance()
    return retrieval.search_requirements(objective_slug, query, k)

def search_legal(objective_slug: str, query: str, k: int = 8) -> List[Dict]:
    """Função de conveniência para busca de normas legais"""
    retrieval = get_retrieval_instance()
    return retrieval.search_legal(objective_slug, query, k)

