"""Tests for the Machine KB consumer (kb, kb_format, kb_fetch, server tools)."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from openwebnet_mcp import kb_fetch, server
from openwebnet_mcp import _paths as paths_mod
from openwebnet_mcp._paths import get_kb_dir
from openwebnet_mcp.kb import KBError, MachineKB, clean_statement
from openwebnet_mcp.kb_format import format_record, format_status

_APP = {"domain": "protocol", "state": "applies", "target": "OpenWebNet WHO 2", "version": {"state": "unknown"}}


def _rec(kind: str, rid: str, **extra):
    base = {
        "id": rid,
        "kind": kind,
        "label": extra.pop("label", rid),
        "applicability": _APP,
        "epistemic_status": extra.pop("epistemic_status", "specified"),
        "confidence": "high",
        "provenance": [
            {
                "evidence_class": "canonical_documentation",
                "location": {"path": "functional/who-2/dimensions.md", "section_id": "ownkb:section:d1:s1"},
            }
        ],
        "cautions": [],
        "questions": [],
        "relationships": [],
    }
    base.update(extra)
    return base


def _write_jsonl(path: Path, records: list[dict]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = "".join(json.dumps(r, sort_keys=True) + "\n" for r in records).encode()
    path.write_bytes(data)  # bytes: text mode would rewrite newlines on Windows and change the hash
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def kb_dir(tmp_path: Path) -> Path:
    root = tmp_path / "knowledge"
    chunk = {
        "id": "ownkb:chunk:r000001",
        "kind": "retrieval_chunk",
        "label": "Shutter level",
        "section_id": "ownkb:section:d1:s1",
        "section_path": ["DIMENSION 10", "Shutter level"],
        "source_path": "functional/who-2/dimensions.md",
        "namespace_context": {"area": "functional"},
        "provenance": {"evidence_class": "canonical_documentation"},
        "qualification_cues": {"uncertainty_cues": ["unknown"], "caution_cues": [], "applicability_cues": []},
        "reference_ids": [],
        "text": "| `255` | Unknown position |",
    }
    claims = [
        _rec("claim", "ownkb:claim:c000001", label="Target level", statement="255 is not a target position.",
             cautions=["ownkb:caution:k000001"], questions=["ownkb:question:q000001"], value={"state": "known"}),
        _rec("claim", "ownkb:claim:c000002", label="Open volume", statement="Volume step size is unresolved.",
             epistemic_status="unresolved", value={"state": "unresolved", "reason": "no capture"}),
        _rec("claim", "ownkb:claim:c000003", label="Leaky table",
             statement="Table context: {'text': 'Scope', 'inline': []} | more", value={"state": "known"}),
    ]
    refs = {
        "cautions": [_rec("caution", "ownkb:caution:k000001", text="Do not merge namespaces.")],
        "questions": [_rec("question", "ownkb:question:q000001", text="Which capture?", resolution_state="open")],
    }
    hashes = {
        "retrieval/chunks.jsonl": _write_jsonl(root / "retrieval" / "chunks.jsonl", [chunk]),
        "claims/claims.jsonl": _write_jsonl(root / "claims" / "claims.jsonl", claims),
    }
    artifacts = [
        {"kind": "retrieval_chunks", "path": "knowledge/retrieval/chunks.jsonl", "sha256": hashes["retrieval/chunks.jsonl"]},
        {"kind": "claim_records", "path": "knowledge/claims/claims.jsonl", "sha256": hashes["claims/claims.jsonl"]},
        {"kind": "schema", "path": "knowledge/schema/record.schema.json", "sha256": "0" * 64},
    ]
    for name in ("cautions", "entities", "glossary", "namespaces", "questions", "relationships", "sources"):
        digest = _write_jsonl(root / "reference" / f"{name}.jsonl", refs.get(name, []))
        artifacts.append({"kind": "reference_registry", "path": f"knowledge/reference/{name}.jsonl", "sha256": digest})
    manifest = {
        "schema_compatibility_version": "0.1.0",
        "generator_version": "test",
        "input_content_sha256": "abc",
        "artifacts": artifacts,
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


def test_load_search_and_lookup(kb_dir):
    kb = MachineKB(kb_dir)
    assert kb.load() and kb.hashes_verified
    hits = kb.search("shutter unknown position 255")
    assert hits[0]["id"] == "ownkb:chunk:r000001"
    assert kb.search("volume", kind="claim", epistemic_status="unresolved")[0]["id"] == "ownkb:claim:c000002"
    assert kb.search("volume", epistemic_status="specified") == []
    assert kb.search("255", area="functional", kind="chunk")
    assert kb.search("255", area="protocol") == []
    assert kb.search("!!!") == []
    assert kb.get("ownkb:caution:k000001")["text"].startswith("Do not")
    assert kb.get("ownkb:missing") is None
    status = kb.status()
    assert status["claims"] == 3 and status["claims_with_degraded_statement"] == 1


def test_degraded_statement_points_to_chunk(kb_dir):
    kb = MachineKB(kb_dir)
    kb.load()
    text, degraded = clean_statement(kb.claims["ownkb:claim:c000003"]["statement"])
    assert degraded and "{'text'" not in text
    assert clean_statement("plain")[1] is False
    assert kb.chunk_for_claim(kb.claims["ownkb:claim:c000003"])["id"] == "ownkb:chunk:r000001"


def test_hash_mismatch_warns_but_strict_refuses(kb_dir):
    (kb_dir / "reference" / "sources.jsonl").write_bytes(b'{"id":"ownkb:source:s1","kind":"source"}\n')
    kb = MachineKB(kb_dir)
    assert kb.load() and not kb.hashes_verified
    assert kb.hash_mismatches == ["knowledge/reference/sources.jsonl"]
    strict = MachineKB(kb_dir, strict=True)
    assert not strict.load() and "SHA-256 mismatch" in strict.load_error


def test_unsupported_version_and_missing(kb_dir, tmp_path, monkeypatch):
    manifest = json.loads((kb_dir / "manifest.json").read_text())
    manifest["schema_compatibility_version"] = "1.0.0"
    (kb_dir / "manifest.json").write_text(json.dumps(manifest))
    kb = MachineKB(kb_dir)
    assert not kb.load() and "not supported" in kb.load_error

    monkeypatch.setattr("openwebnet_mcp.kb.get_kb_dir", lambda: None)
    missing = MachineKB()
    assert not missing.load() and "OPENWEBNET_KB_PATH" in missing.load_error
    assert "false" in format_status(missing.status())

    with pytest.raises(KBError):
        MachineKB(tmp_path)._load_from(tmp_path)


def test_get_kb_dir_env(kb_dir, monkeypatch):
    monkeypatch.setenv("OPENWEBNET_KB_PATH", str(kb_dir))
    assert get_kb_dir() == kb_dir
    monkeypatch.setenv("OPENWEBNET_KB_PATH", str(kb_dir.parent))  # Encyclopedia-root style
    assert get_kb_dir() == kb_dir


def test_kb_fetch_verifies_and_writes(kb_dir, tmp_path, monkeypatch):
    monkeypatch.setattr(kb_fetch, "get_cache_dir", lambda: tmp_path / "cache")
    manifest = (kb_dir / "manifest.json").read_bytes()
    files = {"knowledge/manifest.json": manifest}
    for art in json.loads(manifest)["artifacts"]:
        if art["kind"] != "schema":
            files[art["path"]] = (kb_dir.parent / art["path"]).read_bytes()
    monkeypatch.setattr(kb_fetch, "_download", lambda tag, path: files[path])
    out = kb_fetch.fetch("t1")
    assert (out / "claims" / "claims.jsonl").is_file()
    assert MachineKB(out).load()  # schema entries are skipped on load

    files["knowledge/claims/claims.jsonl"] = b"tampered"
    with pytest.raises(ValueError, match="mismatch"):
        kb_fetch.fetch("t2")
    assert not (tmp_path / "cache" / "machine-kb" / "t2").exists()
    assert kb_fetch.main(["t2"]) == 1


@pytest.mark.asyncio
async def test_server_tools(kb_dir, monkeypatch):
    monkeypatch.setenv("OPENWEBNET_KB_PATH", str(kb_dir))
    res = await server.search_knowledge("target level 255", kind="claim")
    assert "ownkb:claim:c000001" in res and "Do not merge namespaces." in res and "Which capture?" in res

    res = await server.search_knowledge("volume step", kind="claim")
    assert "an open question, not an established fact" in res and "no capture" in res

    res = await server.search_knowledge("leaky table", kind="claim")
    assert "known Machine KB 0.1.0 rendering defect" in res and "ownkb:chunk:r000001" in res

    assert "**Error**" in await server.search_knowledge("x", kind="bogus")
    assert "absence of a record is not a negative assertion" in await server.search_knowledge("zzzqqq")
    assert "shutter" in (await server.get_knowledge_record("ownkb:chunk:r000001")).lower()
    assert "Do not merge" in await server.get_knowledge_record("ownkb:caution:k000001")
    assert "**Error**" in await server.get_knowledge_record("ownkb:nope")
    assert "`true`" in await server.get_knowledge_status()
    assert json.loads(await server.resource_kb_manifest())["generator_version"] == "test"

    summary = await server.rescan_documentation()
    assert "Machine KB" in summary and "loaded" in summary


@pytest.mark.asyncio
async def test_server_tools_without_kb(monkeypatch):
    monkeypatch.setattr("openwebnet_mcp.kb.get_kb_dir", lambda: None)
    assert "**Error**" in await server.search_knowledge("anything")
    assert "**Error**" in await server.get_knowledge_record("ownkb:claim:c1")
    assert "error" in json.loads(await server.resource_kb_manifest())
    assert "`false`" in await server.get_knowledge_status()


def test_format_keeps_version_expression_and_namespace(kb_dir):
    kb = MachineKB(kb_dir)
    kb.load()
    claim = dict(kb.claims["ownkb:claim:c000001"])
    claim["applicability"] = {**_APP, "version": {"state": "specified", "expression": "ZigBee spec 4.0"}}
    claim["context"] = {"description": "WHAT selector", "namespace_id": "ownkb:namespace:who"}
    out = format_record(claim, kb)
    assert "specified: ZigBee spec 4.0" in out and "`ownkb:namespace:who`" in out
    claim["applicability"] = {**_APP, "state": "not_applicable", "reason": "MH200 only"}
    assert "MH200 only" in format_record(claim, kb)


def test_cache_prefers_newest_release(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENWEBNET_KB_PATH", raising=False)
    monkeypatch.setattr(paths_mod, "get_project_root", lambda: tmp_path / "repo" / "x")
    monkeypatch.setattr(paths_mod, "get_cache_dir", lambda: tmp_path / "cache")
    for tag in ("machine-kb-v0.9.0", "machine-kb-v0.10.0"):
        d = tmp_path / "cache" / "machine-kb" / tag / "knowledge"
        d.mkdir(parents=True)
        (d / "manifest.json").write_text("{}")
    assert get_kb_dir().parent.name == "machine-kb-v0.10.0"
    sibling = tmp_path / "repo" / "OpenWebNet-Encyclopedia" / "knowledge"
    sibling.mkdir(parents=True)
    (sibling / "manifest.json").write_text("{}")
    assert get_kb_dir().parent.name == "machine-kb-v0.10.0"  # verified cache beats an unverified checkout
    monkeypatch.setattr(paths_mod, "get_cache_dir", lambda: tmp_path / "empty-cache")
    assert get_kb_dir() == sibling


def test_known_gap_only_for_matching_release(kb_dir):
    kb = MachineKB(kb_dir)
    kb.load()
    assert "Not covered" not in format_status(kb.status())
    status = kb.status()
    status["input_content_sha256"] = "4b652103102613bf8d1c83deabf174364e311e35f88feda453e19845a171aa2c"
    assert "DALI / WHO 24" in format_status(status)


def test_second_leak_shape_is_truncated():
    assert clean_statement('Table: {"text": "Scope"} | more')[1] is True


def test_id_registry_aliases_and_lifecycle(kb_dir):
    registry = {
        "aliases": [{"alias": "ownkb:claim:old", "canonical_id": "ownkb:claim:c000001", "reason": "merged", "first_release": "0.2.0"}],
        "ids": [
            {"id": "ownkb:claim:c000002", "lifecycle": "deprecated", "reason": "superseded wording", "first_release": "0.1.0"},
            {"id": "ownkb:claim:gone", "lifecycle": "retired", "reason": "split", "first_release": "0.1.0",
             "last_release": "0.1.0", "replaced_by": ["ownkb:claim:c000001"]},
        ],
    }
    data = json.dumps(registry).encode()
    (kb_dir / "id-registry.json").write_bytes(data)
    manifest = json.loads((kb_dir / "manifest.json").read_text())
    manifest["artifacts"].append(
        {"kind": "id_registry", "path": "knowledge/id-registry.json", "sha256": hashlib.sha256(data).hexdigest()}
    )
    (kb_dir / "manifest.json").write_text(json.dumps(manifest))
    kb = MachineKB(kb_dir)
    assert kb.load() and kb.hashes_verified
    rec, note = kb.lookup("ownkb:claim:old")
    assert rec["id"] == "ownkb:claim:c000001" and "alias" in note
    rec, note = kb.lookup("ownkb:claim:c000002")
    assert rec["id"] == "ownkb:claim:c000002" and "deprecated" in note
    rec, note = kb.lookup("ownkb:claim:gone")
    assert rec["id"] == "ownkb:claim:c000001" and "retired" in note and "replacement" in note
    assert kb.lookup("ownkb:claim:c000001") == (kb.claims["ownkb:claim:c000001"], None)
    assert kb.lookup("ownkb:claim:nope") == (None, None)


def _set_artifact(kb_dir, kind, path=None):
    manifest = json.loads((kb_dir / "manifest.json").read_text())
    if path is None:
        manifest["artifacts"] = [a for a in manifest["artifacts"] if a["kind"] != kind]
    else:
        for art in manifest["artifacts"]:
            if art["kind"] == kind:
                art["path"] = path
    (kb_dir / "manifest.json").write_text(json.dumps(manifest))


def test_manifest_paths_are_contained_and_required(kb_dir):
    _set_artifact(kb_dir, "claim_records", "knowledge/../../evil.jsonl")
    kb = MachineKB(kb_dir)
    assert not kb.load() and "escapes" in kb.load_error
    _set_artifact(kb_dir, "claim_records", "elsewhere/claims.jsonl")
    assert "outside knowledge/" in _load_error(kb_dir)
    _set_artifact(kb_dir, "claim_records")
    assert "no claim_records" in _load_error(kb_dir)


def _load_error(kb_dir):
    kb = MachineKB(kb_dir)
    assert not kb.load()
    return kb.load_error


def test_manifest_path_is_followed_when_layout_moves(kb_dir):
    (kb_dir / "moved").mkdir()
    (kb_dir / "claims" / "claims.jsonl").rename(kb_dir / "moved" / "c.jsonl")
    _set_artifact(kb_dir, "claim_records", "knowledge/moved/c.jsonl")
    assert MachineKB(kb_dir).load()


def test_kb_fetch_rejects_bad_tag_and_paths(kb_dir, tmp_path, monkeypatch):
    monkeypatch.setattr(kb_fetch, "get_cache_dir", lambda: tmp_path / "cache")
    for tag in ("../x", "a/b", ""):
        with pytest.raises(ValueError, match="invalid tag"):
            kb_fetch.fetch(tag)
    bad = {"artifacts": [{"kind": "claim_records", "path": "knowledge/../../x", "sha256": "0"}]}
    monkeypatch.setattr(kb_fetch, "_download", lambda tag, path: json.dumps(bad).encode())
    with pytest.raises(ValueError, match="unsafe manifest path"):
        kb_fetch.fetch("t3")
    assert not (tmp_path / "cache" / "machine-kb" / "t3").exists()


@pytest.mark.asyncio
async def test_failed_first_load_is_retried(kb_dir, monkeypatch):
    monkeypatch.setattr("openwebnet_mcp.kb.get_kb_dir", lambda: None)
    assert "**Error**" in await server.search_knowledge("shutter")
    monkeypatch.setattr("openwebnet_mcp.kb.get_kb_dir", lambda: kb_dir)
    server._kb_cache.clear()
    assert "ownkb:chunk:r000001" in await server.search_knowledge("shutter")


def test_exact_what_and_dimension_references_are_boosted():
    kb = MachineKB()
    kb.claims = {
        # Plenty of bare 19s, but not the reference being asked for.
        "ownkb:claim:noise": _rec("claim", "ownkb:claim:noise", label="Counter 19 19 19",
                                  statement="channel 19 counts 19 events; what happens at 19 is logged; who cares"),
        "ownkb:claim:hit": _rec("claim", "ownkb:claim:hit", label="Fault", statement="WHAT 19 signals a fault."),
        "ownkb:claim:dim": _rec("claim", "ownkb:claim:dim", label="Setpoint", statement="`DIMENSION 14` writes the setpoint."),
        "ownkb:claim:who14": _rec("claim", "ownkb:claim:who14", label="Lock", statement="WHO 14 setpoint setpoint lock."),
    }
    kb.chunks = {
        "ownkb:chunk:c4": {"id": "ownkb:chunk:c4", "kind": "retrieval_chunk", "label": "Overview", "section_id": "s",
                           "section_path": ["Overview"], "source_path": "functional/who-4-temperature-control/x.md",
                           "text": "Thermoregulation overview."},
    }
    kb._build_index()
    assert kb.search("WHAT 19")[0]["id"] == "ownkb:claim:hit"
    assert kb.search("dim 14 setpoint")[0]["id"] == "ownkb:claim:dim"
    assert kb.search("WHO 4 overview")[0]["id"] == "ownkb:chunk:c4"  # WHO taken from the source path
    assert kb.search("WHAT-19")[0]["id"] == "ownkb:claim:hit"


def test_catalog_who1_timed_and_blink_commands():
    who1 = next(f for f in json.loads(
        (Path(paths_mod.__file__).parent / "data" / "who_catalog.json").read_text(encoding="utf-8")
    )["families"] if f["who"] == 1)
    what = who1["what_commands"]
    assert what["11"] == "Timed ON for 1 minute" and what["15"] == "Timed ON for 5 minutes"
    assert "unresolved" in what["17"] and what["30"].startswith("Increase") and what["31"].startswith("Decrease")
    assert "Dim UP" not in json.dumps(what) and "Toggle" not in json.dumps(what)


@pytest.mark.network
@pytest.mark.skipif(os.environ.get("OPENWEBNET_LIVE_TESTS") != "1", reason="set OPENWEBNET_LIVE_TESTS=1 to hit GitHub")
def test_kb_fetch_live_release(tmp_path, monkeypatch):
    monkeypatch.setattr(kb_fetch, "get_cache_dir", lambda: tmp_path)
    out = kb_fetch.fetch()  # machine-kb-v0.1.0 from raw.githubusercontent.com, every artifact hash-verified
    kb = MachineKB(out, strict=True)
    assert kb.load() and kb.hashes_verified
    assert (len(kb.chunks), len(kb.claims)) == (1173, 7449)
    top = kb.search("WHO 1 WHAT 17", kind="claim", limit=2)
    assert "WHAT 17" in kb.claims[top[0]["id"]]["label"]
