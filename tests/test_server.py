"""Tests for FastMCP server endpoints and resources."""

import pytest
from unittest.mock import patch
from openwebnet_mcp import server


@pytest.mark.asyncio
async def test_tool_search_documentation():
    # Valid query
    res = await server.search_documentation("transition speed")
    assert "Search Results" in res
    assert "transition" in res.lower()

    # Empty / whitespace query does not crash and returns results
    res_empty = await server.search_documentation("   ")
    assert "Search Results" in res_empty
    assert "Relevance Score" in res_empty

    # Empty match query
    res_none = await server.search_documentation("xyz_unmatched_term_qwerty")
    assert "No documentation sections matched" in res_none

    # Caching hit
    res_cached = await server.search_documentation("transition speed")
    assert "Search Results" in res_cached


@pytest.mark.asyncio
async def test_tool_get_who_spec():
    res_1 = await server.get_who_spec(1)
    assert "WHO = 1: Lighting" in res_1
    assert "WHAT Commands" in res_1

    # Cached hit
    res_1_cached = await server.get_who_spec(1)
    assert res_1 == res_1_cached

    # Unknown WHO
    res_unknown = await server.get_who_spec(9999)
    assert "**Error**" in res_unknown


@pytest.mark.asyncio
async def test_tool_list_who_catalog():
    res = await server.list_who_catalog()
    assert "# OpenWebNet Master WHO Catalog" in res
    assert "| **1** | Lighting" in res
    assert "| **2** | Automation" in res


@pytest.mark.asyncio
async def test_tool_get_ha_guide():
    res = await server.get_ha_guide("lighting")
    assert "Lighting Platform Configuration" in res

    # Cached hit
    res_cached = await server.get_ha_guide("lighting")
    assert res == res_cached

    # Unknown guide
    res_unknown = await server.get_ha_guide("non_existent_topic")
    assert "**Error**" in res_unknown


@pytest.mark.asyncio
async def test_tool_lookup_frame_syntax():
    res = await server.lookup_frame_syntax()
    assert "# OpenWebNet Protocol Syntax Reference" in res
    assert "STATUS_EVENT" in res
    assert "DIMENSION_WRITING" in res

    # With filter and who
    res_filtered = await server.lookup_frame_syntax(frame_type="STATUS_EVENT", who=1)
    assert "STATUS_EVENT" in res_filtered
    assert "WHO=1" in res_filtered


@pytest.mark.asyncio
async def test_tool_parse_and_validate_frame():
    # Valid lighting frame
    res_light = await server.parse_and_validate_frame("*1*1*12##")
    assert "- **Valid Grammar**: `YES`" in res_light
    assert "Lighting: Turn ON" in res_light

    # Valid climate frame
    res_climate = await server.parse_and_validate_frame("*#4*1*0*0215##")
    assert "- **Valid Grammar**: `YES`" in res_climate
    assert "Measured Temperature" in res_climate

    # Invalid frame syntax
    res_invalid = await server.parse_and_validate_frame("*invalid*frame##")
    assert "- **Valid Grammar**: `NO`" in res_invalid
    assert "Unrecognized OpenWebNet syntax" in res_invalid


@pytest.mark.asyncio
async def test_tool_draft_own_frame():
    # Valid draft
    res = await server.draft_own_frame(who=1, command_type="command", where="12", what=1)
    assert "Drafted OpenWebNet Frame: `*1*1*12##`" in res
    assert "- **Valid**: `YES`" in res

    # Invalid draft type
    res_err = await server.draft_own_frame(who=1, command_type="unknown", where="12")
    assert "**Error**" in res_err


@pytest.mark.asyncio
async def test_tool_draft_ha_config():
    res = await server.draft_ha_config(platform="light", name="Hallway Light", where="14", dimmable=True, transition=3)
    assert "lights:" in res
    assert 'where: "14"' in res
    assert "dimmable: true" in res

    # Binary sensor draft
    res_bin = await server.draft_ha_config(platform="binary_sensor", name="Front Door Contact", where="31", device_class="door")
    assert "binary_sensor:" in res_bin
    assert "binary_sensors:" in res_bin
    assert "class: door" in res_bin
    assert 'where: "31"' in res_bin


@pytest.mark.asyncio
async def test_tool_get_code_signature():
    res = await server.get_code_signature("MyHOMELight")
    assert "# `MyHOMELight`" in res
    assert "async_turn_on" in res

    # Class.method lookup
    res_method = await server.get_code_signature("MyHOMELight.async_turn_on")
    assert "MyHOMELight.async_turn_on" in res_method
    assert "async def async_turn_on" in res_method

    # Cached hit
    res_cached = await server.get_code_signature("MyHOMELight")
    assert res == res_cached


@pytest.mark.asyncio
async def test_tool_rescan_documentation():
    res = await server.rescan_documentation()
    assert "# OpenWebNet Documentation Rescan Complete" in res
    assert "WHO Families Loaded" in res


@pytest.mark.asyncio
async def test_resources():
    # Resource who-catalog
    res_cat = await server.resource_who_catalog()
    assert "# OpenWebNet Master WHO Catalog" in res_cat

    # Resource protocol-grammar
    res_grammar = await server.resource_protocol_grammar()
    assert "OpenWebNet" in res_grammar

    # Resource toc
    res_toc = await server.resource_docs_toc()
    assert "Documentation Table of Contents" in res_toc

    # Resource guide
    res_guide = await server.resource_guide("lighting")
    assert "Lighting Platform Configuration" in res_guide

    # Resource unknown guide
    res_unknown = await server.resource_guide("unknown_topic")
    assert "not found" in res_unknown


def test_async_ttl_cache():
    cache = server.AsyncTTLCache("test_cache", ttl_seconds=1, maxsize=2)
    
    # Test capacity eviction
    async def dummy(v):
        return v

    import asyncio
    v1 = asyncio.run(cache.get_or_set("k1", dummy, "val1"))
    v2 = asyncio.run(cache.get_or_set("k2", dummy, "val2"))
    v3 = asyncio.run(cache.get_or_set("k3", dummy, "val3"))

    assert len(cache.cache) <= 2
    assert "k1" not in cache.cache  # Evicted LRU entry

    # Test purge expired
    cache.cache["k2"] = ("val2", 0)  # expired timestamp
    cache.purge_expired()
    assert "k2" not in cache.cache


def test_main_entrypoint(monkeypatch):
    monkeypatch.setattr(server.mcp, "run", lambda: None)
    server.main()


@pytest.mark.asyncio
async def test_server_tool_exceptions(monkeypatch):
    # search_documentation error
    with monkeypatch.context() as m:
        m.setattr(server, "_get_doc_indexer", lambda: (_ for _ in ()).throw(RuntimeError("Doc error")))
        res = await server.search_documentation("test")
        assert "**Error**" in res

    # get_who_spec error
    with monkeypatch.context() as m:
        m.setattr(server, "_get_catalog", lambda: (_ for _ in ()).throw(RuntimeError("Catalog error")))
        res = await server.get_who_spec(1)
        assert "**Error**" in res

    # list_who_catalog error
    with monkeypatch.context() as m:
        m.setattr(server, "_get_catalog", lambda: (_ for _ in ()).throw(RuntimeError("List error")))
        res = await server.list_who_catalog()
        assert "**Error**" in res

    # get_ha_guide error
    with monkeypatch.context() as m:
        m.setattr(server, "_get_doc_indexer", lambda: (_ for _ in ()).throw(RuntimeError("Guide error")))
        res = await server.get_ha_guide("lighting")
        assert "**Error**" in res

    # lookup_frame_syntax error
    with monkeypatch.context() as m:
        m.setattr(server, "get_protocol_grammar_path", lambda: (_ for _ in ()).throw(RuntimeError("Grammar error")))
        res = await server.lookup_frame_syntax()
        assert "**Error**" in res

    # parse_and_validate_frame error
    with monkeypatch.context() as m:
        m.setattr(server, "_get_parser", lambda: (_ for _ in ()).throw(RuntimeError("Parser error")))
        res = await server.parse_and_validate_frame("*1*1*12##")
        assert "**Error**" in res

    # draft_own_frame error
    with monkeypatch.context() as m:
        m.setattr(server, "_get_generator", lambda: (_ for _ in ()).throw(RuntimeError("Gen error")))
        res = await server.draft_own_frame(who=1, command_type="command", where="12", what=1)
        assert "**Error**" in res

    # draft_ha_config error
    with monkeypatch.context() as m:
        m.setattr(server, "_get_generator", lambda: (_ for _ in ()).throw(RuntimeError("Draft error")))
        res = await server.draft_ha_config(platform="light", name="Test", where="1")
        assert "**Error**" in res

    # get_code_signature error
    with monkeypatch.context() as m:
        m.setattr(server, "_get_ast_indexer", lambda: (_ for _ in ()).throw(RuntimeError("AST error")))
        res = await server.get_code_signature("Test")
        assert "**Error**" in res

    # rescan_documentation error
    with monkeypatch.context() as m:
        m.setattr(server, "_get_rescan_manager", lambda: (_ for _ in ()).throw(RuntimeError("Rescan error")))
        res = await server.rescan_documentation()
        assert "**Error**" in res


def test_flushing_file_handler_oserror(tmp_path, monkeypatch):
    log_file = tmp_path / "test.log"
    handler = server.FlushingFileHandler(log_file, mode="a", encoding="utf-8")
    
    import logging
    record = logging.LogRecord("test", logging.INFO, "test.py", 10, "test message", (), None)
    
    with monkeypatch.context() as m:
        m.setattr(server.os, "fsync", lambda fd: (_ for _ in ()).throw(OSError("Simulated fsync failure")))
        handler.emit(record)
    
def test_async_ttl_cache_expiration():
    cache = server.AsyncTTLCache("test_exp", ttl_seconds=0, maxsize=5)
    async def fetch(x):
        return x
    
    import asyncio
    import time
    asyncio.run(cache.get_or_set("k", fetch, "initial"))
    time.sleep(0.02)
    val2 = asyncio.run(cache.get_or_set("k", fetch, "refreshed"))
    assert val2 == "refreshed"


@pytest.mark.asyncio
async def test_lookup_frame_syntax_missing_grammar(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "get_protocol_grammar_path", lambda: tmp_path / "missing.json")
    res = await server.lookup_frame_syntax()
    assert "**Error**" in res


def test_prompt_boost():
    # Verify prompt_boost function
    boost_text = server.prompt_boost(topic="lighting")
    assert "OpenWebNet & Home Assistant MyHOME AI Agent Context Boost" in boost_text
    assert "lighting" in boost_text
    assert "WHO=1" in boost_text
    assert "myhome.yaml" in boost_text


@pytest.mark.asyncio
async def test_draft_ha_config_with_gateway():
    res = await server.draft_ha_config(
        platform="light",
        name="Study Dimmer",
        where="23",
        dimmable=True,
        gateway_id="mh202",
        mac="00:03:50:11:22:33",
    )
    assert "mh202:" in res
    assert "00:03:50:11:22:33" in res
    assert "light:" in res
    assert "study_dimmer:" in res


def test_main_and_dunder_main(monkeypatch):
    called = []
    monkeypatch.setattr(server.mcp, "run", lambda: called.append("run"))

    server.main()
    assert called == ["run"]

    # Test __main__ module
    import runpy
    called.clear()
    runpy.run_module("openwebnet_mcp", run_name="__main__")
    assert called == ["run"]

