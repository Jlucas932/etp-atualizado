import unittest
import json
from unittest.mock import patch, MagicMock

# Adicionar o caminho do projeto ao sys.path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.main.python.adapter.entrypoint.etp.EtpDynamicController import etp_dynamic_bp
from src.main.python.domain.interfaces.dataprovider.DatabaseConfig import db
from src.main.python.domain.dto.EtpDto import EtpSession

class ConversationFlowTest(unittest.TestCase):

    def setUp(self):
        """Configura o ambiente de teste."""
        self.app = MagicMock()
        self.app.register_blueprint(etp_dynamic_bp)
        self.client = self.app.test_client()

        # Mock do banco de dados
        self.db_session_patch = patch("src.main.python.domain.interfaces.dataprovider.DatabaseConfig.db.session")
        self.mock_db_session = self.db_session_patch.start()

    def tearDown(self):
        """Limpa o ambiente de teste."""
        self.db_session_patch.stop()

    def test_conversation_flow_advances_stage(self):
        """Testa se o fluxo da conversa avança corretamente de estágio."""
        # 1. Inicia a sessão e define a necessidade
        with patch("src.main.python.adapter.entrypoint.etp.EtpDynamicController.search_requirements") as mock_search:
            mock_search.return_value = []
            with patch("src.main.python.adapter.entrypoint.etp.EtpDynamicController.etp_generator.client.chat.completions.create") as mock_openai:
                # Mock da resposta do OpenAI para a sugestão de requisitos
                mock_openai.return_value.choices[0].message.content = json.dumps({
                    "requirements": [
                        {"id": "1", "text": "Requisito de teste 1"},
                        {"id": "2", "text": "Requisito de teste 2"}
                    ]
                })

                # Simula a primeira mensagem do usuário
                response = self.client.post("/conversation", json={
                    "message": "Preciso de um sistema de gestão de frotas.",
                    "session_id": None
                })

                self.assertEqual(response.status_code, 200)
                data = response.get_json()
                self.assertEqual(data["conversation_stage"], "review_requirement_progressive")
                session_id = data["session_id"]

                # 2. Usuário aceita o requisito
                response = self.client.post("/conversation", json={
                    "message": "ok",
                    "session_id": session_id
                })

                self.assertEqual(response.status_code, 200)
                data = response.get_json()
                # O estágio deve avançar para a revisão do próximo requisito
                self.assertEqual(data["conversation_stage"], "review_requirement_progressive")
                self.assertEqual(data["current_index"], 1)

if __name__ == "__main__":
    unittest.main()

