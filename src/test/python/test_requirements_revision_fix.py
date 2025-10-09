import unittest

from domain.services.requirements_interpreter import (
    normalize_pt,
    detect_requirements_discussion,
    parse_update_command,
    only_lines_R_hash,
    apply_update_command,
    format_for_ui,
)
from domain.dto.EtpDto import EtpDto
from domain.usecase.etp.dynamic_prompt_generator import (
    generate_requirements_rag_first,
    regenerate_single,
)


class TestRequirementsFlow(unittest.TestCase):
    def test_only_lines_format(self):
        raw = ["R1: Um", "- Dois", "3) Três."]
        out = only_lines_R_hash(raw)
        self.assertEqual(out[0]["text"], "R1 — Um")
        self.assertEqual(out[1]["text"], "R2 — Dois")
        self.assertEqual(out[2]["text"], "R3 — Três")

    def test_ui_mapping_hides_justification(self):
        out = format_for_ui(only_lines_R_hash(["A", "B"]))
        self.assertFalse(out[0]["showJustificativa"])
        self.assertIsNone(out[0]["justification"])

    def test_parse_accept(self):
        cmd = parse_update_command("pode manter, está ok pra mim")
        self.assertEqual(cmd["type"], "accept_all")

    def test_parse_replace_one(self):
        cmd = parse_update_command("troca o R3 por um requisito sobre monitoramento em tempo real")
        self.assertEqual(cmd["type"], "replace_one")
        self.assertEqual(cmd["targets"], [3])

    def test_apply_replace_one(self):
        cur = only_lines_R_hash(["A", "B", "C"])
        cmd = {"type": "replace_one", "targets": [2], "payload": "BB"}
        new_list = apply_update_command(cmd, cur)
        self.assertEqual([r["text"] for r in new_list], ["R1 — A", "R2 — BB", "R3 — C"])

    def test_flow_regenerate_single(self):
        cur = only_lines_R_hash(["A", "B", "C"])
        new_list = regenerate_single("qualquer necessidade", cur, 1)
        self.assertEqual(len(new_list), 3)


if __name__ == "__main__":
    unittest.main()
