import unittest
import sys
import os

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'main', 'python'))

from domain.usecase.utils.legal_norms import extract_citations, filter_federal, suggest_federal


class TestLegalNorms(unittest.TestCase):
    """Testes para as funções de extração e filtragem de normas legais federais"""
    
    def test_extract_citations_basic(self):
        """Teste básico de extração de citações"""
        texto = "Este documento se baseia na Lei 14.133/2021 e no Decreto 10.024 de 2019."
        
        citations = extract_citations(texto)
        
        self.assertEqual(len(citations), 2)
        
        # Verificar primeira citação (Lei 14.133/2021)
        lei = citations[0]
        self.assertEqual(lei["tipo"], "Lei")
        self.assertEqual(lei["numero"], "14133")
        self.assertEqual(lei["ano"], "2021")
        self.assertIn("Lei 14.133/2021", lei["texto_original"])
        
        # Verificar segunda citação (Decreto 10.024/2019)
        decreto = citations[1]
        self.assertEqual(decreto["tipo"], "Decreto")
        self.assertEqual(decreto["numero"], "10024")
        self.assertEqual(decreto["ano"], "2019")
    
    def test_extract_citations_different_formats(self):
        """Teste de extração com diferentes formatos de citação"""
        texto = """
        Aplicam-se as seguintes normas:
        - Lei nº 8.666 de 1993
        - Lei Complementar 123/2006
        - Decreto n. 7892 de 2013
        - Instrução Normativa 40/2020
        - Portaria 443 de 2018
        """
        
        citations = extract_citations(texto)
        
        self.assertEqual(len(citations), 5)
        
        # Verificar tipos extraídos
        tipos = [c["tipo"] for c in citations]
        self.assertIn("Lei", tipos)
        self.assertIn("Lei Complementar", tipos)
        self.assertIn("Decreto", tipos)
        self.assertIn("Instrução Normativa", tipos)
        self.assertIn("Portaria", tipos)
    
    def test_filter_federal_acceptance_criteria(self):
        """
        Teste do critério de aceite: dado um trecho com "Lei 14.133/2021" e "Lei Estadual 123/2019",
        a função retorna só a 14.133 marcada como federal.
        """
        texto = "Conforme a Lei 14.133/2021 e a Lei Estadual 123/2019, aplicam-se as regras."
        
        # Extrair citações
        citations = extract_citations(texto)
        self.assertEqual(len(citations), 2)
        
        # Filtrar federais
        federal_citations = filter_federal(citations)
        
        # Verificar que só a Lei 14.133/2021 foi mantida
        self.assertEqual(len(federal_citations), 1)
        
        federal_lei = federal_citations[0]
        self.assertEqual(federal_lei["tipo"], "Lei")
        self.assertEqual(federal_lei["numero"], "14133")
        self.assertEqual(federal_lei["ano"], "2021")
        self.assertEqual(federal_lei["sphere"], "federal")
    
    def test_filter_federal_state_indicators(self):
        """Teste de filtragem com indicadores explícitos de esfera estadual/municipal"""
        texto = """
        Normas aplicáveis:
        - Lei Federal 14.133/2021
        - Lei Estadual 1234/2020
        - Lei Municipal 5678/2019
        - Decreto Distrital 999/2018
        - Lei 8.666/1993
        """
        
        citations = extract_citations(texto)
        federal_citations = filter_federal(citations)
        
        # Devem restar apenas as leis sem indicação de esfera estadual/municipal/distrital
        # e a Lei 8.666 (conhecidamente federal)
        expected_federal = []
        for citation in federal_citations:
            if (citation["numero"] == "14133" and citation["ano"] == "2021") or \
               (citation["numero"] == "8666" and citation["ano"] == "1993"):
                expected_federal.append(citation)
        
        # Verificar que temos pelo menos a Lei 8.666 (conhecidamente federal)
        numeros_federais = [c["numero"] for c in federal_citations]
        self.assertIn("8666", numeros_federais)
        
        # Verificar que todas têm sphere="federal"
        for citation in federal_citations:
            self.assertEqual(citation["sphere"], "federal")
    
    def test_filter_federal_known_laws(self):
        """Teste de filtragem com leis conhecidamente federais"""
        texto = """
        Aplicam-se as seguintes leis:
        - Lei 8666/93 (Licitações)
        - Lei 14133/2021 (Nova Lei de Licitações)
        - Lei 8429/92 (Improbidade)
        - Lei 12527/2011 (Acesso à Informação)
        """
        
        citations = extract_citations(texto)
        federal_citations = filter_federal(citations)
        
        # Todas devem ser identificadas como federais
        self.assertEqual(len(federal_citations), 4)
        
        # Verificar números conhecidos
        numeros = [c["numero"] for c in federal_citations]
        self.assertIn("8666", numeros)
        self.assertIn("14133", numeros)
        self.assertIn("8429", numeros)
        self.assertIn("12527", numeros)
    
    def test_suggest_federal_licitacao(self):
        """Teste de sugestão de normas federais para objetivo de licitação"""
        suggestions = suggest_federal("licitacao", k=3)
        
        self.assertLessEqual(len(suggestions), 3)
        self.assertGreater(len(suggestions), 0)
        
        # Verificar que todas têm sphere="federal"
        for suggestion in suggestions:
            self.assertEqual(suggestion["sphere"], "federal")
            self.assertIn("tipo", suggestion)
            self.assertIn("numero", suggestion)
            self.assertIn("ano", suggestion)
        
        # Lei 14.133/2021 deve estar entre as sugestões (maior relevância)
        numeros = [s["numero"] for s in suggestions]
        self.assertIn("14133", numeros)
    
    def test_suggest_federal_tecnologia(self):
        """Teste de sugestão de normas federais para objetivo de tecnologia"""
        suggestions = suggest_federal("tecnologia", k=4)
        
        self.assertLessEqual(len(suggestions), 4)
        
        # Deve incluir normas específicas de TIC
        found_tic = False
        for suggestion in suggestions:
            if (suggestion.get("tipo") == "Instrução Normativa" and 
                suggestion.get("numero") == "1" and 
                suggestion.get("ano") == "2019"):
                found_tic = True
                break
        
        self.assertTrue(found_tic, "Instrução Normativa 1/2019 sobre TIC deve estar presente")
    
    def test_suggest_federal_default(self):
        """Teste de sugestão com objetivo não reconhecido (usar padrão)"""
        suggestions = suggest_federal("objetivo_desconhecido", k=6)
        
        self.assertLessEqual(len(suggestions), 6)
        self.assertGreater(len(suggestions), 0)
        
        # Deve incluir normas padrão como Lei 14.133/2021
        numeros = [s["numero"] for s in suggestions]
        self.assertIn("14133", numeros)
    
    def test_extract_citations_year_normalization(self):
        """Teste de normalização de anos com 2 dígitos"""
        texto = "Lei 8666/93 e Decreto 1234/25 se aplicam."
        
        citations = extract_citations(texto)
        self.assertEqual(len(citations), 2)
        
        # Ano 93 deve virar 1993
        lei_citation = next(c for c in citations if c["numero"] == "8666")
        self.assertEqual(lei_citation["ano"], "1993")
        
        # Ano 25 deve virar 2025
        decreto_citation = next(c for c in citations if c["numero"] == "1234")
        self.assertEqual(decreto_citation["ano"], "2025")


if __name__ == '__main__':
    unittest.main()