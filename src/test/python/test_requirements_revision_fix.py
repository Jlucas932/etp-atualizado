"""Testes determinísticos para revisão de requisitos do ETP."""

import unittest
from unittest.mock import patch, MagicMock

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'main', 'python'))

from domain.services.requirements_interpreter import (
    parse_update_command,
    apply_update_command,
    format_requirements_list,
)
from domain.dto.EtpDto import EtpSession
from domain.services.requirements_interpreter import detect_requirements_discussion
from domain.usecase.etp.dynamic_prompt_generator import DynamicPromptGenerator
from adapter.entrypoint.chat.ChatController import _default_requirements_from_need


class RequirementsInterpreterTest(unittest.TestCase):
    def setUp(self):
        self.requirements = [
            {"id": "R1", "text": "Garantir integração com o ERP corporativo"},
            {"id": "R2", "text": "Manter registros de auditoria por 24 meses"},
            {"id": "R3", "text": "Disponibilizar painel de monitoramento diário"},
        ]

    def test_accept_intent(self):
        command = parse_update_command("aceitar", self.requirements)
        self.assertEqual(command["intent"], "accept")
        updated, message = apply_update_command(command, self.requirements)
        self.assertEqual(updated, self.requirements)
        self.assertIn("Requisitos confirmados", message)

    def test_refazer_all_intent(self):
        command = parse_update_command("refazer tudo", self.requirements)
        self.assertEqual(command["intent"], "refazer_all")

    def test_edit_range(self):
        command = parse_update_command("ajustar R1-R2 para logs assinados", self.requirements)
        self.assertEqual(command["intent"], "edit")
        self.assertEqual(command["targets"], [1, 2])
        updated, _ = apply_update_command(command, self.requirements)
        self.assertEqual(updated[0]["text"], "logs assinados")
        self.assertEqual(updated[1]["text"], "logs assinados")

    def test_reinforce_command(self):
        command = parse_update_command("reforça o último com SLA de 99%", self.requirements)
        self.assertEqual(command["intent"], "reinforce")
        updated, message = apply_update_command(command, self.requirements)
        self.assertIn("Reforcei", message)
        self.assertIn("99%", updated[-1]["text"])

    def test_insert_command(self):
        command = parse_update_command("inserir requisito sobre LGPD", self.requirements)
        self.assertEqual(command["intent"], "insert")
        updated, _ = apply_update_command(command, self.requirements)
        self.assertEqual(len(updated), 4)
        self.assertTrue(updated[-1]["text"].lower().startswith("requisito"))

    def test_format_list_without_justification(self):
        formatted = format_requirements_list(self.requirements)
        self.assertNotIn("Justificativa", formatted)
        self.assertTrue(formatted.startswith("R1 —"))

    def test_detect_discussion(self):
        self.assertTrue(detect_requirements_discussion("remover R2"))
        self.assertFalse(detect_requirements_discussion("qual o valor estimado?"))


class EtpSessionRequirementTest(unittest.TestCase):
    def setUp(self):
        self.session = EtpSession()

    def test_sanitize_requirements(self):
        raw = [
            {"id": "R1", "text": "Texto", "justification": "deve sumir"},
            {"id": "R2", "text": "Outro"},
        ]
        self.session.set_requirements(raw)
        stored = self.session.get_requirements()
        self.assertEqual(len(stored), 2)
        self.assertNotIn("justification", stored[0])
        self.assertEqual(stored[0]["id"], "R1")

    def test_lock_flag(self):
        self.assertFalse(self.session.is_requirements_locked())
        self.session.set_requirements_locked(True)
        self.assertTrue(self.session.is_requirements_locked())


class RagFirstGenerationTest(unittest.TestCase):
    @patch('domain.usecase.etp.dynamic_prompt_generator.openai.OpenAI')
    def test_rag_results_are_prioritized(self, mock_openai):
        generator = DynamicPromptGenerator('test')
        generator.client = MagicMock()

        class FakeRag:
            def search_requirements(self, objective_slug, query, k=12):
                return [
                    {"content": "Implementar backups diários", "hybrid_score": 0.9},
                    {"content": "Manter criptografia de dados", "hybrid_score": 0.85},
                ]

        generator.set_rag_retrieval(FakeRag())

        with patch.object(generator, '_clean_and_format_rag_content', side_effect=lambda c: c):
            with patch.object(generator, '_generate_requirements_with_llm') as mock_llm:
                result = generator.generate_requirements_with_rag("backup", "serviço")
                mock_llm.assert_not_called()

        requirements = result["requirements"]
        self.assertEqual(len(requirements), 2)
        self.assertTrue(all(req["id"].startswith('R') for req in requirements))
        self.assertEqual(result["source"], "rag")

    @patch('domain.usecase.etp.dynamic_prompt_generator.openai.OpenAI')
    def test_fallback_to_llm_when_rag_empty(self, mock_openai):
        generator = DynamicPromptGenerator('test')
        generator.client = MagicMock()
        generator.set_rag_retrieval(MagicMock(search_requirements=lambda *args, **kwargs: []))

        mocked_lines = ["Requisito 1", "Requisito 2", "Requisito 3", "Requisito 4", "Requisito 5"]
        with patch.object(generator, '_clean_and_format_rag_content', side_effect=lambda c: c):
            with patch.object(generator, '_generate_requirements_with_llm', return_value=(mocked_lines, "")) as mock_llm:
                result = generator.generate_requirements_with_rag("novo sistema", "serviço")
                mock_llm.assert_called_once()
        self.assertEqual(len(result["requirements"]), 5)
        self.assertEqual(result["source"], "llm")


class DefaultRequirementsTest(unittest.TestCase):
    def test_default_requirements_builder(self):
        defaults = _default_requirements_from_need("gestão de frota")
        self.assertGreaterEqual(len(defaults), 5)
        self.assertTrue(all(req["id"].startswith("R") for req in defaults))
        self.assertTrue(all("gestão" in req["text"].lower() or "frota" in req["text"].lower() for req in defaults))


if __name__ == '__main__':
    unittest.main()
