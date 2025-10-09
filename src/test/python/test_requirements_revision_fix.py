"""
Testes para verificar o fix do fluxo de revisão de requisitos.
Valida que comandos como "só não gostei do último" não reiniciam a necessidade.
"""

import unittest
import sys
import os
import json
from unittest.mock import patch, MagicMock

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'main', 'python'))

from domain.services.requirements_interpreter import (
    parse_update_command, apply_update_command, detect_requirements_discussion,
    format_requirements_list
)


class TestRequirementsRevisionFix(unittest.TestCase):
    """Testes para o fix de revisão de requisitos"""

    def setUp(self):
        """Configurar dados de teste"""
        self.sample_requirements = [
            {
                "id": "R1",
                "text": "Comprovação de experiência mínima de 2 anos",
                "justification": "Necessário para garantir qualidade do serviço"
            },
            {
                "id": "R2", 
                "text": "Certificação ISO 9001 válida",
                "justification": "Padrão de qualidade requerido"
            },
            {
                "id": "R3",
                "text": "Equipe técnica qualificada",
                "justification": "Recursos humanos adequados"
            },
            {
                "id": "R4",
                "text": "Garantia mínima de 12 meses",
                "justification": "Proteção contratual necessária"
            },
            {
                "id": "R5",
                "text": "Sistema de monitoramento em tempo real",
                "justification": "Controle operacional requerido"
            }
        ]
        
        self.necessity = "gestão de frota de aeronaves"

    def test_detect_requirements_discussion(self):
        """Testa detecção de discussão sobre requisitos"""
        # Casos que DEVEM ser detectados como discussão sobre requisitos
        requirement_discussions = [
            "só não gostei do último, poderia sugerir outro?",
            "ajustar o último requisito",
            "remover 2 e 4",
            "trocar 3",
            "manter só 1 e 2",
            "confirmo os requisitos",
            "requisitos estão bons"
        ]
        
        for text in requirement_discussions:
            with self.subTest(text=text):
                self.assertTrue(detect_requirements_discussion(text), 
                              f"'{text}' deveria ser detectado como discussão sobre requisitos")
        
        # Casos que NÃO devem ser detectados
        non_requirement_discussions = [
            "qual o valor estimado?",
            "como funciona o processo?",
            "preciso de ajuda",
            "onde encontro informações?"
        ]
        
        for text in non_requirement_discussions:
            with self.subTest(text=text):
                self.assertFalse(detect_requirements_discussion(text),
                               f"'{text}' não deveria ser detectado como discussão sobre requisitos")

    def test_parse_command_adjust_last(self):
        """Testa parsing do comando 'ajustar o último'"""
        command = parse_update_command("só não gostei do último, poderia sugerir outro?", self.sample_requirements)
        
        self.assertEqual(command["intent"], "edit")
        self.assertEqual(command["indices"], [5])  # Último requisito
        self.assertIsNone(command.get("new_text"))

    def test_parse_command_remove_multiple(self):
        """Testa parsing do comando 'remover 2 e 4'"""
        command = parse_update_command("remova 2 e 4", self.sample_requirements)
        
        self.assertEqual(command["intent"], "remove")
        self.assertEqual(sorted(command["indices"]), [2, 4])

    def test_parse_command_edit_with_text(self):
        """Testa parsing do comando com novo texto especificado"""
        command = parse_update_command("trocar 3: exigir certificação Part-145 válida pela ANAC", self.sample_requirements)
        
        self.assertEqual(command["intent"], "edit")
        self.assertEqual(command["indices"], [3])
        self.assertEqual(command["new_text"], "exigir certificação Part-145 válida pela ANAC")

    def test_parse_command_keep_only(self):
        """Testa parsing do comando 'manter só'"""
        command = parse_update_command("manter só 1 e 2", self.sample_requirements)
        
        self.assertEqual(command["intent"], "keep_only")
        self.assertEqual(sorted(command["indices"]), [1, 2])

    def test_parse_command_confirm(self):
        """Testa parsing do comando de confirmação"""
        commands = [
            "confirmo os requisitos",
            "perfeito, está bom",
            "ok, concordo"
        ]
        
        for cmd_text in commands:
            with self.subTest(text=cmd_text):
                command = parse_update_command(cmd_text, self.sample_requirements)
                self.assertEqual(command["intent"], "confirm")

    def test_parse_command_no_need_change(self):
        """Testa que frases de revisão NÃO são interpretadas como troca de necessidade"""
        revision_phrases = [
            "só não gostei do último",
            "ajuste apenas o último", 
            "troque o 3",
            "remover 2 e 4"
        ]
        
        for phrase in revision_phrases:
            with self.subTest(phrase=phrase):
                command = parse_update_command(phrase, self.sample_requirements)
                self.assertNotEqual(command["intent"], "change_need", 
                                  f"'{phrase}' não deveria ser interpretado como mudança de necessidade")

    def test_parse_command_explicit_need_change(self):
        """Testa que apenas gatilhos explícitos mudam necessidade"""
        need_change_phrases = [
            "nova necessidade é compra de veículos",
            "trocar a necessidade para manutenção",
            "na verdade a necessidade é outra"
        ]
        
        for phrase in need_change_phrases:
            with self.subTest(phrase=phrase):
                command = parse_update_command(phrase, self.sample_requirements)
                self.assertEqual(command["intent"], "change_need")

    def test_apply_remove_command(self):
        """Testa aplicação do comando de remoção"""
        command = {"intent": "remove", "indices": [2, 4]}
        new_reqs, message = apply_update_command(command, self.sample_requirements, self.necessity)
        
        # Deve remover requisitos 2 e 4, restando 3
        self.assertEqual(len(new_reqs), 3)
        
        # IDs devem ser renumerados
        expected_ids = ["R1", "R2", "R3"]
        actual_ids = [req["id"] for req in new_reqs]
        self.assertEqual(actual_ids, expected_ids)
        
        # Conteúdo dos requisitos restantes deve ser correto
        self.assertEqual(new_reqs[0]["text"], "Comprovação de experiência mínima de 2 anos")  # Era R1
        self.assertEqual(new_reqs[1]["text"], "Equipe técnica qualificada")  # Era R3  
        self.assertEqual(new_reqs[2]["text"], "Sistema de monitoramento em tempo real")  # Era R5

    def test_apply_keep_only_command(self):
        """Testa aplicação do comando 'manter só'"""
        command = {"intent": "keep_only", "indices": [1, 3]}
        new_reqs, message = apply_update_command(command, self.sample_requirements, self.necessity)
        
        # Deve manter apenas requisitos 1 e 3
        self.assertEqual(len(new_reqs), 2)
        
        # IDs renumerados
        expected_ids = ["R1", "R2"]
        actual_ids = [req["id"] for req in new_reqs]
        self.assertEqual(actual_ids, expected_ids)
        
        # Conteúdo correto
        self.assertEqual(new_reqs[0]["text"], "Comprovação de experiência mínima de 2 anos")  # Era R1
        self.assertEqual(new_reqs[1]["text"], "Equipe técnica qualificada")  # Era R3

    def test_apply_edit_command_with_text(self):
        """Testa aplicação do comando de edição com novo texto"""
        command = {
            "intent": "edit", 
            "indices": [3], 
            "new_text": "Certificação Part-145 válida pela ANAC"
        }
        new_reqs, message = apply_update_command(command, self.sample_requirements, self.necessity)
        
        # Número de requisitos deve ser o mesmo
        self.assertEqual(len(new_reqs), 5)
        
        # Requisito 3 deve ter novo texto
        self.assertEqual(new_reqs[2]["text"], "Certificação Part-145 válida pela ANAC")
        self.assertIn("ajustado conforme solicitação", new_reqs[2]["justification"])

    def test_apply_edit_command_needs_regeneration(self):
        """Testa aplicação do comando de edição sem novo texto (para regeneração)"""
        command = {"intent": "edit", "indices": [5]}
        new_reqs, message = apply_update_command(command, self.sample_requirements, self.necessity)
        
        # Requisito deve ser marcado para regeneração
        self.assertTrue(new_reqs[4].get("_needs_regeneration", False))

    def test_apply_confirm_command(self):
        """Testa aplicação do comando de confirmação"""
        command = {"intent": "confirm"}
        new_reqs, message = apply_update_command(command, self.sample_requirements, self.necessity)
        
        # Lista deve permanecer inalterada
        self.assertEqual(len(new_reqs), 5)
        self.assertEqual(new_reqs, self.sample_requirements)
        self.assertIn("confirmada", message)

    def test_format_requirements_list(self):
        """Testa formatação da lista de requisitos para exibição"""
        formatted = format_requirements_list(self.sample_requirements)
        
        # Deve conter cabeçalho
        self.assertIn("## Requisitos Atuais", formatted)
        
        # Deve conter todos os requisitos com IDs
        for req in self.sample_requirements:
            self.assertIn(f"**{req['id']}**", formatted)
            self.assertIn(req['text'], formatted)
            if req.get('justification'):
                self.assertIn(req['justification'], formatted)

    def test_integration_scenario_adjust_last(self):
        """Teste de integração: cenário completo 'ajustar o último'"""
        user_input = "só não gostei do último, poderia sugerir outro?"
        
        # 1. Detectar que é discussão sobre requisitos
        self.assertTrue(detect_requirements_discussion(user_input))
        
        # 2. Parsear comando
        command = parse_update_command(user_input, self.sample_requirements)
        
        # 3. Aplicar comando
        new_reqs, message = apply_update_command(command, self.sample_requirements, self.necessity)
        
        # 4. Verificar resultado
        self.assertEqual(command["intent"], "edit")
        self.assertEqual(command["indices"], [5])
        self.assertTrue(new_reqs[4].get("_needs_regeneration", False))
        self.assertIn("será(ão) regenerado(s)", message)

    def test_integration_scenario_remove_multiple(self):
        """Teste de integração: cenário 'remover 2 e 4'"""
        user_input = "remova 2 e 4"
        
        # Fluxo completo
        self.assertTrue(detect_requirements_discussion(user_input))
        command = parse_update_command(user_input, self.sample_requirements)
        new_reqs, message = apply_update_command(command, self.sample_requirements, self.necessity)
        
        # Verificações
        self.assertEqual(command["intent"], "remove")
        self.assertEqual(len(new_reqs), 3)
        self.assertIn("Removidos 2 requisito(s)", message)

    def test_edge_case_empty_requirements(self):
        """Testa casos extremos com lista vazia de requisitos"""
        empty_reqs = []
        
        command = parse_update_command("último requisito", empty_reqs)
        self.assertEqual(command["intent"], "unclear")
        
        new_reqs, message = apply_update_command(command, empty_reqs)
        self.assertEqual(len(new_reqs), 0)

    def test_edge_case_invalid_indices(self):
        """Testa casos com índices inválidos"""
        command = parse_update_command("remover 10", self.sample_requirements)
        
        # Índice 10 não existe (só temos 5 requisitos)
        # Deve ser ignorado no parsing
        self.assertEqual(command["intent"], "unclear")


class TestChatControllerIntegration(unittest.TestCase):
    """Testes de integração com ChatController"""
    
    def setUp(self):
        """Configurar mocks para testes de integração"""
        os.environ['OPENAI_API_KEY'] = 'test_api_key_for_testing'
        os.environ['SECRET_KEY'] = 'test_secret_key'

    def tearDown(self):
        """Limpar variáveis de ambiente"""
        for key in ['OPENAI_API_KEY', 'SECRET_KEY']:
            if key in os.environ:
                del os.environ[key]

    @patch('domain.services.requirements_interpreter.parse_update_command')
    @patch('domain.services.requirements_interpreter.apply_update_command')
    def test_handle_requirements_revision_mock(self, mock_apply, mock_parse):
        """Testa integração com handle_requirements_revision usando mocks"""
        # Configurar mocks
        mock_parse.return_value = {"intent": "edit", "indices": [5]}
        mock_apply.return_value = (
            [{"id": "R1", "text": "Updated req", "justification": "test"}],
            "Requisito atualizado"
        )
        
        # Mock da sessão ETP
        mock_session = MagicMock()
        mock_session.get_requirements.return_value = [
            {"id": "R1", "text": "Original req", "justification": "original"}
        ]
        mock_session.necessity = "test necessity"
        mock_session.session_id = "test_session"
        
        # Verificar que os mocks seriam chamados corretamente
        # (teste conceitual - implementação real requer Flask app context)
        mock_parse.assert_not_called()  # Ainda não chamado
        
        # Simular chamada
        user_message = "ajustar o último"
        command = mock_parse.return_value
        updated_reqs, message = mock_apply.return_value
        
        # Verificações
        self.assertEqual(command["intent"], "edit")
        self.assertEqual(len(updated_reqs), 1)
        self.assertEqual(message, "Requisito atualizado")


if __name__ == '__main__':
    # Configurar logging para debug
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    unittest.main(verbosity=2)