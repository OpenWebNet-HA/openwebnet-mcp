"""Markdown rendering of Machine KB records, keeping every qualification visible."""

from __future__ import annotations

from typing import Any

from openwebnet_mcp.kb import NON_ESTABLISHED, MachineKB, clean_statement

_SNIPPET_CHARS = 600

# Coverage gaps announced with a release, keyed by manifest input_content_sha256 so they cannot go stale.
KNOWN_GAPS = {
    "4b652103102613bf8d1c83deabf174364e311e35f88feda453e19845a171aa2c": "DALI / WHO 24",  # machine-kb-v0.1.0
}


def _provenance_line(prov: dict[str, Any], kb: MachineKB) -> str:
    loc = prov.get("location", {})
    where = f"{loc.get('path', '?')} ({loc.get('section_id', '?')})"
    source = prov.get("source_id")
    tail = f" — source: {kb.registry_label(source)} `{source}`" if source else ""
    return f"`{prov.get('evidence_class', '?')}` @ {where}{tail}"


def _applicability(app: dict[str, Any]) -> str:
    version = app.get("version", {})
    ver = version.get("state", "unknown")
    if "expression" in version:
        ver = f"{ver}: {version['expression']}"
    line = f"{app.get('state', '?')} — {app.get('domain', '?')} / {app.get('target', '?')} (version {ver})"
    if app.get("reason"):
        line += f" — {app['reason']}"
    return line


def _hydrate(ids: list[str], kb: MachineKB, field: str) -> list[str]:
    lines = []
    for rid in ids:
        rec = kb.registry.get(rid)
        if not rec:
            lines.append(f"- `{rid}` (not in registry)")
            continue
        extra = f" [{rec['resolution_state']}]" if "resolution_state" in rec else ""
        lines.append(f"- `{rid}`{extra}: {rec.get(field) or rec.get('label', '')}")
    return lines


def format_claim(claim: dict[str, Any], kb: MachineKB, *, detail: bool = True) -> str:
    statement, degraded = clean_statement(claim.get("statement", ""))
    status = claim.get("epistemic_status", "?")
    lines = [f"### `{claim['id']}` — {claim.get('label', '')}", f"> {statement}", ""]
    status_line = f"- **Epistemic status**: `{status}`"
    if status in NON_ESTABLISHED:
        status_line += f" — {NON_ESTABLISHED[status]}"
    lines.append(status_line + f" | **Confidence**: `{claim.get('confidence', '?')}`")
    lines.append(f"- **Applicability**: {_applicability(claim.get('applicability', {}))}")
    context = claim.get("context", {})
    if context:
        # Equal numbers in different namespaces are not the same thing; keep the namespace visible.
        lines.append(f"- **Context**: {context.get('description', '')} (`{context.get('namespace_id', '?')}`)")
    value = claim.get("value", {})
    if value.get("state") not in (None, "known"):
        lines.append(f"- **Value**: `{value['state']}` — {value.get('reason', 'no reason given')}")
    if detail:
        for prov in claim.get("provenance", []):
            lines.append(f"- **Provenance**: {_provenance_line(prov, kb)}")
    else:
        prov = (claim.get("provenance") or [{}])[0]
        lines.append(f"- **Provenance**: {_provenance_line(prov, kb)}")
    if claim.get("cautions"):
        lines.append("- **Cautions**:")
        lines += [f"  {ln}" for ln in _hydrate(claim["cautions"], kb, "text")]
    if claim.get("questions"):
        lines.append("- **Open questions**:")
        lines += [f"  {ln}" for ln in _hydrate(claim["questions"], kb, "text")]
    links = claim.get("claim_links", {})
    for rel in ("contradicts", "qualifies", "supports"):
        if links.get(rel):
            lines.append(f"- **{rel.title()}**: " + ", ".join(f"`{i}`" for i in links[rel]))
    if degraded:
        chunk = kb.chunk_for_claim(claim)
        pointer = f"`{chunk['id']}`" if chunk else "the source section"
        lines.append(
            "- **Note**: this claim statement is truncated by a known Machine KB 0.1.0 rendering "
            f"defect (Encyclopedia#37); read {pointer} (`get_knowledge_record`) for the intact text."
        )
    return "\n".join(lines)


def format_chunk(chunk: dict[str, Any], kb: MachineKB, *, detail: bool = True) -> str:
    path = " › ".join(chunk.get("section_path", []))
    text = chunk.get("text", "")
    if not detail and len(text) > _SNIPPET_CHARS:
        text = text[:_SNIPPET_CHARS].rstrip() + " […]"
    cues = chunk.get("qualification_cues", {})
    lines = [
        f"### `{chunk['id']}` — {path}",
        f"- **Source**: `{chunk.get('source_path', '?')}` (section `{chunk.get('section_id', '?')}`)",
        f"- **Area**: `{chunk.get('namespace_context', {}).get('area', '?')}`"
        f" | **Evidence**: `{chunk.get('provenance', {}).get('evidence_class', '?')}`",
    ]
    for name in ("uncertainty_cues", "caution_cues", "applicability_cues"):
        if cues.get(name):
            lines.append(f"- **{name.replace('_', ' ').title()}**: " + ", ".join(cues[name]))
    if detail and chunk.get("reference_ids"):
        lines.append("- **References**: " + ", ".join(f"`{i}`" for i in chunk["reference_ids"]))
    lines += ["", "```markdown", text, "```"]
    return "\n".join(lines)


def format_registry_record(rec: dict[str, Any], kb: MachineKB) -> str:
    kind = rec.get("kind", "?")
    body = rec.get("text") or rec.get("definition") or rec.get("description") or rec.get("title") or ""
    lines = [f"### `{rec['id']}` — {rec.get('label', '')} ({kind})"]
    if body:
        lines.append(f"> {body}")
    lines.append(f"- **Epistemic status**: `{rec.get('epistemic_status', '?')}`")
    lines.append(f"- **Applicability**: {_applicability(rec.get('applicability', {}))}")
    for key in ("predicate", "resolution_state", "entity_type", "source_type", "publisher"):
        if key in rec:
            lines.append(f"- **{key}**: `{rec[key]}`")
    for key in ("subject_id", "object_id"):
        if key in rec:
            lines.append(f"- **{key}**: `{rec[key]}` ({kb.registry_label(rec[key])})")
    for prov in rec.get("provenance", []):
        lines.append(f"- **Provenance**: {_provenance_line(prov, kb)}")
    if rec.get("cautions"):
        lines.append("- **Cautions**:")
        lines += [f"  {ln}" for ln in _hydrate(rec["cautions"], kb, "text")]
    return "\n".join(lines)


def format_record(rec: dict[str, Any], kb: MachineKB, *, detail: bool = True) -> str:
    kind = rec.get("kind")
    if kind == "claim":
        return format_claim(rec, kb, detail=detail)
    if kind == "retrieval_chunk":
        return format_chunk(rec, kb, detail=detail)
    return format_registry_record(rec, kb)


def format_search(query: str, hits: list[dict[str, Any]], kb: MachineKB) -> str:
    lines = [f"# Machine KB results for '{query}'", ""]
    for hit in hits:
        rec = kb.get(hit["id"])
        if rec is None:  # pragma: no cover - index and stores are built together
            continue
        lines.append(f"_rank score `{hit['score']}` (lexical relevance, not evidence strength)_")
        lines.append(format_record(rec, kb, detail=False))
        lines.append("")
    manifest = kb.manifest
    lines.append(
        f"*Machine KB {manifest.get('generator_version', '?')}, schema "
        f"{manifest.get('schema_compatibility_version', '?')}; the human-readable Encyclopedia is authoritative.*"
    )
    return "\n".join(lines)


def format_status(status: dict[str, Any]) -> str:
    if not status["loaded"]:
        return f"# Machine KB status\n\n- **Loaded**: `false`\n- **Reason**: {status['load_error']}"
    integrity = "verified" if status["hashes_verified"] else "MISMATCH — " + ", ".join(status["hash_mismatches"])
    lines = [
        "# Machine KB status",
        "",
        "- **Loaded**: `true`",
        f"- **Location**: `{status['kb_dir']}`",
        f"- **Generator**: `{status['generator_version']}` | **Schema compatibility**: `{status['schema_compatibility_version']}`",
        f"- **Input content SHA-256**: `{status['input_content_sha256']}`",
        f"- **Artifact hashes**: {integrity}",
        f"- **Retrieval chunks**: `{status['chunks']}` | **Claims**: `{status['claims']}`"
        f" (`{status['claims_with_degraded_statement']}` with a degraded statement, Encyclopedia#37)",
        "- **Claims by epistemic status**: "
        + ", ".join(f"`{k}`: {v}" for k, v in status["claims_by_epistemic_status"].items()),
        "- **Reference records**: " + ", ".join(f"`{k}`: {v}" for k, v in status["reference_records"].items()),
    ]
    gap = KNOWN_GAPS.get(status["input_content_sha256"])
    if gap:
        lines += ["", f"Not covered by this KB release: {gap}."]
    return "\n".join(lines)
