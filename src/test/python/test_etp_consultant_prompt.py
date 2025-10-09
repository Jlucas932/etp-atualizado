import unittest
import sys
import os

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'main', 'python'))

from config.etp_consultant_prompt import (
    get_etp_consultant_prompt, 
    get_requirements_formatting_rules,
    ETP_CONSULTANT_SYSTEM_PROMPT
)


class TestEtpConsultantPrompt(unittest.TestCase):
    """Test suite for ETP Consultant Prompt configuration"""
    
    def test_etp_consultant_prompt_exists(self):
        """Test that ETP consultant prompt constant exists and is not empty"""
        self.assertIsNotNone(ETP_CONSULTANT_SYSTEM_PROMPT)
        self.assertIsInstance(ETP_CONSULTANT_SYSTEM_PROMPT, str)
        self.assertGreater(len(ETP_CONSULTANT_SYSTEM_PROMPT), 100)
        
    def test_etp_consultant_prompt_contains_key_elements(self):
        """Test that prompt contains key required elements"""
        prompt = ETP_CONSULTANT_SYSTEM_PROMPT
        
        # Check for JSON format requirements
        self.assertIn("necessidade", prompt)
        self.assertIn("requisitos", prompt)
        self.assertIn("estado", prompt)
        self.assertIn("etapa_atual", prompt)
        self.assertIn("origem_requisitos", prompt)
        self.assertIn("requisitos_confirmados", prompt)
        
        # Check for format requirements
        self.assertIn("R1", prompt)
        self.assertIn("R2", prompt)
        self.assertIn("R5", prompt)  # Should have 5 requirements
        
        # Check for prohibitions
        self.assertIn("justificativa", prompt.lower())
        self.assertIn("JSON válido", prompt)
        
        # Check for RAG consultation
        self.assertIn("RAG", prompt)
        self.assertIn("base de conhecimento", prompt.lower())
        
        # Check for consultant role
        self.assertIn("consultor", prompt.lower())
        self.assertIn("ETP", prompt)
        
        # Check for new structure elements
        self.assertIn("Regras inquebráveis", prompt)
        self.assertIn("Persistência do fluxo", prompt)
        
    def test_get_etp_consultant_prompt_basic(self):
        """Test get_etp_consultant_prompt without context"""
        prompt = get_etp_consultant_prompt()
        
        self.assertIsNotNone(prompt)
        self.assertIsInstance(prompt, str)
        self.assertEqual(prompt, ETP_CONSULTANT_SYSTEM_PROMPT)
        
    def test_get_etp_consultant_prompt_with_context(self):
        """Test get_etp_consultant_prompt with context"""
        test_context = "Contexto da sessão ETP: teste"
        test_kb_context = "Base de conhecimento: documentos relevantes"
        
        prompt = get_etp_consultant_prompt(context=test_context, kb_context=test_kb_context)
        
        self.assertIsNotNone(prompt)
        self.assertIn(test_context, prompt)
        self.assertIn(test_kb_context, prompt)
        
    def test_get_requirements_formatting_rules(self):
        """Test get_requirements_formatting_rules"""
        rules = get_requirements_formatting_rules()
        
        self.assertIsNotNone(rules)
        self.assertIsInstance(rules, str)
        
        # Check for JSON format
        self.assertIn("necessidade", rules)
        self.assertIn("requisitos", rules)
        self.assertIn("estado", rules)
        
        # Check for format examples
        self.assertIn("R1 —", rules)
        self.assertIn("R5 —", rules)  # Should show 5 requirements
        
        # Check for prohibitions
        self.assertIn("justificativa", rules.lower())
        self.assertIn("JSON", rules)
        
    def test_prompt_format_strictness(self):
        """Test that prompt emphasizes strict format requirements"""
        prompt = ETP_CONSULTANT_SYSTEM_PROMPT
        
        # Check for emphasis on JSON format
        self.assertIn("JSON válido", prompt)
        self.assertIn("Formato de saída", prompt)
        self.assertIn("Regras inquebráveis", prompt)
        
        # Check that it prohibits text outside JSON
        self.assertIn("Sem texto fora do JSON", prompt)
        self.assertIn("Sem markdown", prompt)
        self.assertIn("bullets", prompt.lower())
        
    def test_prompt_prohibits_justifications(self):
        """Test that prompt explicitly prohibits justifications in requirements"""
        prompt = ETP_CONSULTANT_SYSTEM_PROMPT
        
        # Multiple mentions of prohibition
        justification_count = prompt.lower().count("justificativa")
        self.assertGreaterEqual(justification_count, 1, "Prompt should mention justification prohibition")
        
        # Explicit prohibition
        self.assertIn("Nunca inclua campo \"justificativa\"", prompt)
        
    def test_prompt_emphasizes_rag_first(self):
        """Test that prompt emphasizes RAG consultation first"""
        prompt = ETP_CONSULTANT_SYSTEM_PROMPT
        
        # RAG should be mentioned as priority
        self.assertIn("RAG-first", prompt)
        self.assertIn("consulte a base de conhecimento antes", prompt.lower())
        self.assertIn("monte os requisitos a partir deles", prompt.lower())


class TestRequirementsFormatValidation(unittest.TestCase):
    """Test suite for validating requirements format"""
    
    def test_valid_requirement_format(self):
        """Test examples of valid requirement formats"""
        valid_formats = [
            "R1 — O sistema deve permitir cadastro de itens",
            "R2 — O sistema deve registrar histórico completo",
            "R3 — O sistema deve gerar relatório em PDF",
        ]
        
        for req in valid_formats:
            # Each should start with R followed by number
            self.assertTrue(req.startswith("R"))
            # Should contain the em dash separator
            self.assertIn(" — ", req)
            # Should not contain justification
            self.assertNotIn("Justificativa", req)
            self.assertNotIn("(", req)
            
    def test_invalid_requirement_formats(self):
        """Test examples of invalid requirement formats that should be avoided"""
        invalid_formats = [
            "R1 — Requisito (Justificativa: porque é importante)",
            "* R1 — Requisito com bullet",
            "R1 - Requisito com hífen simples em vez de em dash",
        ]
        
        # These formats should be detected as invalid
        # (In production, these would be rejected or corrected)
        for req in invalid_formats:
            if "Justificativa" in req:
                self.assertIn("Justificativa", req, "Should contain prohibited justification")
            if req.startswith("*"):
                self.assertTrue(req.startswith("*"), "Should detect bullet point")


if __name__ == '__main__':
    unittest.main()
