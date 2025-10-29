import sys
import os

# Add src path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'main', 'python'))

from domain.usecase.etp.legal_basis_interpreter import parse_legal_basis

def test_legal_basis_flow():
    assert parse_legal_basis("Lei 14.133/2021, art. 6º", {})['intent'] == 'legal_basis_set'
    assert parse_legal_basis("Observação: caso excepcional", {})['intent'] == 'legal_basis_notes'
    assert parse_legal_basis("Finalizar", {})['intent'] == 'finalize'
