import os
import sys
from dotenv import load_dotenv
from application.config.FlaskConfig import create_api
import logging
from datetime import datetime

# Carregar variáveis de ambiente
load_dotenv()

# Verificar se a API key está configurada
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if not OPENAI_API_KEY or OPENAI_API_KEY == 'sua_api_key_aqui':
    print("❌ ERRO: API Key da OpenAI não configurada!")
    print("")
    print("Para corrigir:")
    print("1. Edite o arquivo '.env'")
    print("2. Substitua 'sua_api_key_aqui' pela sua chave real")
    print("3. Para obter uma API key: https://platform.openai.com/api-keys")
    print("")
    sys.exit(1)

print("✅ API Key configurada com sucesso!")
print(f"🔑 Usando API Key: {OPENAI_API_KEY[:4]}****{OPENAI_API_KEY[-4:]}")

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Criar aplicação Flask (necessário para gunicorn)
create_app = create_api
app = create_app()

if __name__ == "__main__":
    # Criar diretório de logs se não existir
    os.makedirs('logs', exist_ok=True)

    print("🚀 Iniciando servidor ETP Sistema Padronizado (Docker)...")
    print(f"📍 Acesse: http://localhost:5002")
    print("🔄 Para parar o servidor: Ctrl+C")
    print(f"🕒 Iniciado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Inicializar sistema RAG
    with app.app_context():
        try:
            from pathlib import Path
            import openai
            from rag.retrieval import get_retrieval_instance
            
            # Verificar se existem índices FAISS
            index_dir = Path("src/main/python/rag/index/faiss")
            
            if index_dir.exists() and (index_dir / "etp_index.faiss").exists():
                print("🔍 Carregando índices RAG...")
                
                # Configurar cliente OpenAI se disponível
                openai_client = None
                try:
                    openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
                except Exception as e:
                    print(f"⚠️  Aviso: Não foi possível configurar cliente OpenAI: {e}")
                
                # Inicializar sistema de retrieval
                retrieval = get_retrieval_instance(openai_client=openai_client)
                
                if retrieval.build_indices():
                    print("✅ Sistema RAG inicializado com sucesso!")
                else:
                    print("⚠️  Aviso: Falha ao carregar índices RAG")
            else:
                print("📋 Índices RAG não encontrados.")
                print("   Para criar os índices, execute:")
                print("   python -m rag.ingest_etps --rebuild")
                
        except Exception as e:
            print(f"⚠️  Aviso: Erro ao inicializar sistema RAG: {e}")
            print("   A aplicação continuará funcionando sem o sistema RAG.")

    # Executar servidor Flask nativo (Docker)
    app.run(
        host="0.0.0.0",
        port=5002,
        debug=False,  # Desabilitar debug no Docker
        use_reloader=False
    )
