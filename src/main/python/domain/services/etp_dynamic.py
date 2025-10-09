import os
from domain.usecase.etp.etp_generator_dynamic import DynamicEtpGenerator
from domain.usecase.etp.dynamic_prompt_generator import DynamicPromptGenerator
from rag.retrieval import RAGRetrieval


def init_etp_dynamic():
    """Inicializa componentes dinâmicos do ETP."""
    openai_api_key = os.getenv('OPENAI_API_KEY')

    etp_generator = DynamicEtpGenerator(openai_api_key) if openai_api_key else None
    prompt_generator = DynamicPromptGenerator(openai_api_key) if openai_api_key else None

    if prompt_generator and openai_api_key:
        rag_system = RAGRetrieval(openai_client=prompt_generator.client)
        rag_system.build_indices()
        prompt_generator.set_rag_retrieval(rag_system)
    else:
        rag_system = None

    return etp_generator, prompt_generator, rag_system
