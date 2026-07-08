import pytest

from arena_agents.base import AgentError
from arena_agents.mistral import parse_grades


def test_json_pur() -> None:
    assert parse_grades('{"A": 80, "B": 45}', ["A", "B"]) == {"A": 80, "B": 45}


def test_json_dans_du_texte_et_des_fences() -> None:
    text = 'Voici mon evaluation :\n```json\n{"A": 70, "B": 20, "C": 10}\n```\nVoila.'
    assert parse_grades(text, ["A", "B", "C"]) == {"A": 70, "B": 20, "C": 10}


def test_note_manquante_vaut_zero() -> None:
    assert parse_grades('{"A": 50}', ["A", "B"]) == {"A": 50, "B": 0}


def test_note_negative_ou_bizarre_ecrasee() -> None:
    assert parse_grades('{"A": -5, "B": "bof"}', ["A", "B"]) == {"A": 1, "B": 1}


def test_tout_a_zero_devient_egalite() -> None:
    assert parse_grades('{"A": 0, "B": 0}', ["A", "B"]) == {"A": 1, "B": 1}


def test_pas_de_json_leve() -> None:
    with pytest.raises(AgentError, match="JSON"):
        parse_grades("je ne sais pas noter", ["A"])


def test_json_casse_leve() -> None:
    with pytest.raises(AgentError, match="illisible"):
        parse_grades('{"A": 80,,}', ["A"])
