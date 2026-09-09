"""Tests for AstIndexer module."""

import pytest
from pathlib import Path
from openwebnet_mcp.ast_indexer import AstIndexer


def test_ast_builtin_reference():
    indexer = AstIndexer(repo_path=None)
    assert len(indexer._cache) >= 4

    light_sym = indexer.get_symbol("MyHOMELight")
    assert light_sym is not None
    assert "async_turn_on" in light_sym["methods"]
    assert "LightEntityFeature.TRANSITION" in light_sym["supported_features"][0]

    cover_sym = indexer.get_symbol("MyHOMECover")
    assert cover_sym is not None
    assert "async_open_cover" in cover_sym["methods"]

    msg_sym = indexer.get_symbol("OWNMessage")
    assert msg_sym is not None


def test_format_symbol_markdown():
    indexer = AstIndexer(repo_path=None)
    md = indexer.format_symbol_markdown("MyHOMELight")
    assert "# `MyHOMELight`" in md
    assert "async_turn_on" in md
    assert "Supported Entity Features" in md

    # Unknown symbol
    md_err = indexer.format_symbol_markdown("NonExistentClass")
    assert "**Error**" in md_err

    # Symbol with no public methods
    indexer._cache["EmptyClass"] = {
        "class_name": "EmptyClass",
        "module": "test.empty",
        "methods": {},
        "supported_features": [],
    }
    md_empty = indexer.format_symbol_markdown("EmptyClass")
    assert "No public methods found" in md_empty


def test_ast_parsing_complex_signatures(tmp_path):
    repo = tmp_path / "repo"
    custom_comp = repo / "custom_components" / "myhome"
    custom_comp.mkdir(parents=True)

    py_code = """
class ComplexEntity:
    def execute(self, a: int, *args: str, flag: bool = False, **kwargs: dict) -> bool:
        \"\"\"Complex docstring\"\"\"
        return True
"""
    (custom_comp / "complex.py").write_text(py_code, encoding="utf-8")

    # Also write a syntax-broken python file to test resilience
    (custom_comp / "broken.py").write_text("def syntax_error(:", encoding="utf-8")

    indexer = AstIndexer(repo_path=repo)
    sym = indexer.get_symbol("ComplexEntity")
    assert sym is not None
    assert "*args" in sym["methods"]["execute"]
    assert "**kwargs" in sym["methods"]["execute"]
    assert "-> bool" in sym["methods"]["execute"]
