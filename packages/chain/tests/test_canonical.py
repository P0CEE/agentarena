import pytest

from arena_chain.canonical import NonCanonicalError, canonical, tagged_hash


def test_independant_de_l_ordre_d_insertion() -> None:
    a = {"b": 1, "a": {"y": 2, "x": 3}}
    b = {"a": {"x": 3, "y": 2}, "b": 1}
    assert canonical(a) == canonical(b)


def test_float_interdit() -> None:
    with pytest.raises(NonCanonicalError):
        canonical({"amount": 1.5})


def test_float_imbrique_interdit() -> None:
    with pytest.raises(NonCanonicalError):
        canonical({"scores": [1, 2, {"w": [0.5]}]})


def test_cle_non_str_interdite() -> None:
    with pytest.raises(NonCanonicalError):
        canonical({1: "a"})


def test_ascii_pur() -> None:
    out = canonical({"brief": "écris une fonction"})
    assert out == out.decode("ascii").encode("ascii")
    assert b"\\u00e9" in out


def test_separation_de_domaine() -> None:
    assert tagged_hash("tag-a", {"x": 1}) != tagged_hash("tag-b", {"x": 1})


def test_tag_non_confondable_avec_le_contenu() -> None:
    # Le separateur \x00 empeche un contenu de se faire passer pour un tag.
    assert tagged_hash("ab", "c") != tagged_hash("a", "bc")
