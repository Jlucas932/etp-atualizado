import pytest

from domain.usecase.etp.requirements_interpreter import parse_update_command

def test_confirm_intent_variants():
    reqs = ["R1", "R2", "R3"]
    for phrase in ["aceito", "pode seguir", "sem alterações", "ok", "fechou", "confirmo", "manter assim"]:
        out = parse_update_command(phrase, reqs)
        assert out['intent'] == 'confirm'

def test_restart_intent_variants():
    reqs = ["R1", "R2"]
    for phrase in ["reiniciar", "recomeçar", "nova necessidade", "redefinir necessidade"]:
        out = parse_update_command(phrase, reqs)
        assert out['intent'] == 'restart_necessity'

def test_unclear_fallback():
    out = parse_update_command("fale mais sobre isso", ["R1"])
    assert out['intent'] == 'unclear'
