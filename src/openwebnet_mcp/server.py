"""
OpenWebNet-MCP Server — FastMCP Gateway.

Exposes 10 tools and 4 resources for browsing OpenWebNet protocol documentation,
WHO specifications, frame validation, and Home Assistant MyHOME integration knowledge.

Strict stdio fd redirection ensures that stray print() / warnings
never corrupt the JSON-RPC pipeline.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

try:
    from fastmcp import FastMCP
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        from mcp.server.mcpserver import MCPServer as FastMCP

from openwebnet_mcp._paths import get_log_dir, get_protocol_grammar_path
from openwebnet_mcp.ast_indexer import AstIndexer
from openwebnet_mcp.doc_indexer import DocIndexer
from openwebnet_mcp.frame_generator import FrameGenerator
from openwebnet_mcp.frame_parser import FrameParser
from openwebnet_mcp.rescan_manager import RescanManager
from openwebnet_mcp.who_catalog import WhoCatalog

# ── OS-level fd redirection to protect JSON-RPC on stdio ─────────────
_real_stdout_fd = os.dup(sys.stdout.fileno())   # save real fd 1
_real_stderr = sys.stderr
sys.stdout = sys.stderr                          # Python-level guard

logger = logging.getLogger("openwebnet_mcp")

# ── Configure logging: stderr + file ─────────────────────────────────
_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S"))
logger.addHandler(_handler)

_LOG_DIR = get_log_dir()


class FlushingFileHandler(logging.FileHandler):
    """FileHandler that flushes to disk immediately so tails work."""

    def emit(self, record):
        super().emit(record)
        self.flush()
        try:
            os.fsync(self.stream.fileno())
        except OSError:
            pass


_file_handler = FlushingFileHandler(_LOG_DIR / "startup.log", mode="a", encoding="utf-8")
_file_handler.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
logger.addHandler(_file_handler)
logger.setLevel(logging.INFO)


class AsyncTTLCache:
    """Async TTL cache with LRU eviction and active expiry purge."""

    def __init__(self, name: str, ttl_seconds: int, maxsize: int = 256):
        self.name = name
        self.ttl = ttl_seconds
        self.maxsize = maxsize
        self.cache: OrderedDict = OrderedDict()

    async def get_or_set(self, key, coro_func, *args, **kwargs):
        now = time.time()
        if key in self.cache:
            val, expiry = self.cache[key]
            if now < expiry:
                self.cache.move_to_end(key)
                logger.debug("[CACHE HIT] %s (key: %s)", self.name, key)
                return val
            logger.debug("[CACHE EXPIRED] %s (key: %s)", self.name, key)
            del self.cache[key]
        else:
            logger.debug("[CACHE MISS] %s (key: %s)", self.name, key)

        start_time = time.time()
        val = await coro_func(*args, **kwargs)
        elapsed = (time.time() - start_time) * 1000.0
        logger.debug("[CACHE LOAD] %s resolved in %.1fms", self.name, elapsed)

        if not (isinstance(val, str) and val.startswith("**Error**")):
            while len(self.cache) >= self.maxsize:
                evicted_key, _ = self.cache.popitem(last=False)
                logger.debug("[CACHE EVICT] %s (key: %s)", self.name, evicted_key)
            self.cache[key] = (val, now + self.ttl)
        return val

    def purge_expired(self):
        """Actively remove all expired entries."""
        now = time.time()
        expired = [k for k, (_, exp) in self.cache.items() if now >= exp]
        for k in expired:
            del self.cache[k]
            logger.debug("[CACHE PURGE] %s (key: %s)", self.name, k)

    def clear(self):
        self.cache.clear()


# ── Lazy singletons & locks ──────────────────────────────────────────
_catalog: WhoCatalog | None = None
_parser: FrameParser | None = None
_generator: FrameGenerator | None = None
_doc_indexer: DocIndexer | None = None
_ast_indexer: AstIndexer | None = None
_rescan_manager: RescanManager | None = None

_catalog_lock = asyncio.Lock()
_doc_lock = asyncio.Lock()
_ast_lock = asyncio.Lock()

# In-memory caches (10 min TTL)
_doc_search_cache = AsyncTTLCache("doc_search", ttl_seconds=600)
_who_spec_cache = AsyncTTLCache("who_spec", ttl_seconds=600)
_guide_cache = AsyncTTLCache("guide", ttl_seconds=600)
_frame_syntax_cache = AsyncTTLCache("frame_syntax", ttl_seconds=600)
_ast_cache = AsyncTTLCache("ast_symbol", ttl_seconds=600)


def _get_catalog() -> WhoCatalog:
    global _catalog
    if _catalog is None:
        _catalog = WhoCatalog()
    return _catalog


def _get_parser() -> FrameParser:
    global _parser
    if _parser is None:
        _parser = FrameParser(catalog=_get_catalog())
    return _parser


def _get_generator() -> FrameGenerator:
    global _generator
    if _generator is None:
        _generator = FrameGenerator(parser=_get_parser())
    return _generator


def _get_doc_indexer() -> DocIndexer:
    global _doc_indexer
    if _doc_indexer is None:
        _doc_indexer = DocIndexer()
    return _doc_indexer


def _get_ast_indexer() -> AstIndexer:
    global _ast_indexer
    if _ast_indexer is None:
        _ast_indexer = AstIndexer()
    return _ast_indexer


def _get_rescan_manager() -> RescanManager:
    global _rescan_manager
    if _rescan_manager is None:
        _rescan_manager = RescanManager(
            who_catalog=_get_catalog(),
            doc_indexer=_get_doc_indexer(),
            ast_indexer=_get_ast_indexer(),
        )
    return _rescan_manager


# ── FastMCP server definition ────────────────────────────────────────
mcp = FastMCP("openwebnet-mcp")


# ── 1. Search Documentation ──────────────────────────────────────────
@mcp.tool()
async def search_documentation(query: str, category: str | None = None) -> str:
    """Fuzzy and keyword search across OpenWebNet protocol specifications and Home Assistant MyHOME guides.

    Args:
        query: Search keywords or question (e.g. 'lighting transition speed', 'CEN+ blueprint', 'WHO 4').
        category: Optional category filter ('embedded_guide', 'external_reference').
    """
    key = f"{query.strip().lower()}::{category}"

    async def _impl():
        async with _doc_lock:
            indexer = _get_doc_indexer()
            hits = indexer.search(query, category=category, limit=6)

            if not hits:
                return f"No documentation sections matched query: '{query}'."

            lines = [f"# Search Results for '{query}'", ""]
            for h in hits:
                lines.append(f"### {h['heading']} ({h['doc_name']})")
                lines.append(f"**Relevance Score**: `{h['relevance_score']}` | **Category**: `{h['category']}`")
                lines.append(f"```markdown\n{h['snippet']}\n```")
                lines.append(f"*File*: `{h['file_path']}`\n")

            return "\n".join(lines)

    try:
        return await _doc_search_cache.get_or_set(key, _impl)
    except Exception as err:
        logger.error("search_documentation failed: %s", err, exc_info=True)
        return f"**Error**: {err}"


# ── 2. Get WHO Specification ─────────────────────────────────────────
@mcp.tool()
async def get_who_spec(who: int) -> str:
    """Retrieve full technical specification, WHAT commands, and DIMENSIONS for an OpenWebNet WHO family.

    Args:
        who: Numeric WHO identifier (e.g. 1 for Lighting, 2 for Covers, 4 for Climate, 15 for CEN, 16 for Sound, 25 for CEN+).
    """
    key = int(who)

    async def _impl():
        async with _catalog_lock:
            catalog = _get_catalog()
            return catalog.format_family_details(who)

    try:
        return await _who_spec_cache.get_or_set(key, _impl)
    except Exception as err:
        logger.error("get_who_spec failed: %s", err, exc_info=True)
        return f"**Error**: {err}"


# ── 3. List WHO Catalog ──────────────────────────────────────────────
@mcp.tool()
async def list_who_catalog() -> str:
    """Return complete inventory table of all 20+ OpenWebNet WHO families with archive status and HA platform."""
    try:
        catalog = _get_catalog()
        return catalog.format_summary_markdown()
    except Exception as err:
        logger.error("list_who_catalog failed: %s", err, exc_info=True)
        return f"**Error**: {err}"


# ── 4. Get Home Assistant Guide ──────────────────────────────────────
@mcp.tool()
async def get_ha_guide(topic: str) -> str:
    """Fetch complete markdown guide for configuring and troubleshooting Home Assistant entities.

    Args:
        topic: Name of guide/platform (e.g. 'lighting', 'automation_covers', 'climate', 'cen_scenarios', 'energy_sensors', 'sound_system', 'light_transitions', 'advanced_uses', 'troubleshooting').
    """
    key = topic.strip().lower()

    async def _impl():
        async with _doc_lock:
            indexer = _get_doc_indexer()
            guide = indexer.get_guide(topic)
            if not guide:
                return (
                    f"**Error**: No guide found matching topic '{topic}'. "
                    "Available topics include: 'lighting', 'automation_covers', 'climate_thermoregulation', "
                    "'cen_scenarios', 'energy_sensors', 'sound_system', 'light_transitions', "
                    "'advanced_uses', 'troubleshooting_faq'."
                )
            return guide

    try:
        return await _guide_cache.get_or_set(key, _impl)
    except Exception as err:
        logger.error("get_ha_guide failed: %s", err, exc_info=True)
        return f"**Error**: {err}"


# ── 5. Lookup Frame Syntax ───────────────────────────────────────────
@mcp.tool()
async def lookup_frame_syntax(frame_type: str | None = None, who: int | None = None) -> str:
    """Look up OpenWebNet message grammar, regex templates, and parameter formats.

    Args:
        frame_type: Optional filter (e.g. 'STATUS_EVENT', 'STATUS_REQUEST', 'DIMENSION_WRITING', 'DIMENSION_REQUEST').
        who: Optional WHO code to cross-reference examples and addressing schemes.
    """
    key = f"{frame_type}::{who}"

    async def _impl():
        grammar_path = get_protocol_grammar_path()
        if not grammar_path.exists():
            return "**Error**: protocol_grammar.json definition file not found."

        data = json.loads(grammar_path.read_text(encoding="utf-8"))
        lines = [
            f"# OpenWebNet Protocol Syntax Reference",
            "",
            f"- **Protocol**: {data.get('protocol_name')} ({data.get('standard')})",
            f"- **Delimiters**: Start `{data['frame_delimiters']['start']}`, End `{data['frame_delimiters']['end']}`, Field `{data['frame_delimiters']['field_separator']}`, Param `{data['frame_delimiters']['param_separator']}`",
            "",
            "## Frame Formats",
        ]

        types = data.get("frame_types", [])
        if frame_type:
            types = [t for t in types if frame_type.upper() in t["type"].upper()]

        for t in types:
            lines.append(f"### `{t['type']}`")
            lines.append(f"- **Template**: `{t['template']}`")
            lines.append(f"- **Regex Pattern**: `{t['pattern']}`")
            lines.append(f"- **Description**: {t['description']}")
            lines.append(f"- **Examples**: {', '.join(f'`{e}`' for e in t.get('examples', []))}")
            lines.append("")

        lines.append("## Addressing Conventions")
        for name, addr in data.get("addressing_conventions", {}).items():
            lines.append(f"- **{name.replace('_', ' ').title()}** (`{addr['syntax']}`): {addr['description']}")

        if who is not None:
            catalog = _get_catalog()
            fam = catalog.get_family(who)
            if fam:
                lines.extend([
                    "",
                    f"## Addressing & Syntax for WHO={who} ({fam.get('name')})",
                    f"- **Addressing Guide**: {fam.get('addressing')}",
                ])

        return "\n".join(lines)

    try:
        return await _frame_syntax_cache.get_or_set(key, _impl)
    except Exception as err:
        logger.error("lookup_frame_syntax failed: %s", err, exc_info=True)
        return f"**Error**: {err}"


# ── 6. Parse and Validate Frame ──────────────────────────────────────
@mcp.tool()
async def parse_and_validate_frame(frame: str) -> str:
    """Parse a raw OpenWebNet frame string and perform semantic protocol validation.

    Args:
        frame: Raw OpenWebNet frame (e.g. '*1*1*12##', '*#4*1*0*0215##', '*#*1##').
    """
    try:
        parser = _get_parser()
        parsed = parser.parse(frame)

        lines = [
            f"# OpenWebNet Frame Analysis: `{parsed.raw_frame}`",
            "",
            f"- **Valid Grammar**: `{'YES' if parsed.is_valid else 'NO'}`",
            f"- **Frame Type**: `{parsed.frame_type}`",
            f"- **Subsystem (WHO)**: `{parsed.who}`",
            f"- **Address (WHERE)**: `{parsed.where}`" if parsed.where is not None else "- **Address (WHERE)**: `N/A`",
        ]

        if parsed.what is not None:
            what_full = str(parsed.what)
            if parsed.what_params:
                what_full += "#" + "#".join(parsed.what_params)
            lines.append(f"- **Action (WHAT)**: `{what_full}`")

        if parsed.dimension is not None:
            lines.append(f"- **Dimension**: `{parsed.dimension}`")
            lines.append(f"- **Dimension Values**: `{parsed.dimension_values}`")

        lines.extend([
            "",
            "## Explanation",
            parsed.explanation,
        ])

        if parsed.warnings:
            lines.extend(["", "## ⚠️ Warnings"])
            for w in parsed.warnings:
                lines.append(f"- {w}")

        return "\n".join(lines)
    except Exception as err:
        logger.error("parse_and_validate_frame failed: %s", err, exc_info=True)
        return f"**Error**: {err}"


# ── 7. Draft OpenWebNet Frame ────────────────────────────────────────
@mcp.tool()
async def draft_own_frame(
    who: int,
    command_type: str,
    where: str,
    what: int | str | None = None,
    dimension: int | None = None,
    values: list[str] | None = None,
) -> str:
    """Construct and validate a syntactically correct OpenWebNet frame.

    Args:
        who: Subsystem WHO code (1 = Lighting, 2 = Automation, 4 = Climate, etc.).
        command_type: One of 'command', 'status_request', 'dimension_request', 'dimension_writing'.
        where: Device address (e.g. '12', '0', '21#4#1').
        what: Action or WHAT code (e.g. 1 for ON, 0 for OFF).
        dimension: Dimension index (e.g. 1 for level, 0 for temp).
        values: Optional list of values for dimension writes (e.g. ['50', '0'] for 50% brightness).
    """
    try:
        generator = _get_generator()
        frame_str, parsed = generator.build_frame(
            who=who,
            command_type=command_type,
            where=where,
            what=what,
            dimension=dimension,
            values=values,
        )

        lines = [
            f"# Drafted OpenWebNet Frame: `{frame_str}`",
            "",
            f"- **Command Type**: `{command_type}`",
            f"- **Subsystem (WHO)**: `{who}`",
            f"- **Address (WHERE)**: `{where}`",
            f"- **Valid**: `{'YES' if parsed.is_valid else 'NO'}`",
            f"- **Meaning**: {parsed.explanation}",
        ]

        if parsed.warnings:
            lines.extend(["", "## ⚠️ Warnings"])
            for w in parsed.warnings:
                lines.append(f"- {w}")

        return "\n".join(lines)
    except Exception as err:
        logger.error("draft_own_frame failed: %s", err, exc_info=True)
        return f"**Error**: {err}"


# ── 8. Draft Home Assistant Configuration ────────────────────────────
@mcp.tool()
async def draft_ha_config(
    platform: str,
    name: str,
    where: str,
    dimmable: bool = False,
    transition: int | None = None,
    run_time: float | None = None,
    heat_support: bool = True,
    cool_support: bool = False,
    sensor_type: str = "power",
) -> str:
    """Generate production-ready Home Assistant YAML configuration for any MyHOME entity.

    Args:
        platform: Platform type ('light', 'cover', 'climate', 'sensor', 'switch', 'media_player').
        name: Friendly name for the entity (e.g. 'Living Room Dimmer').
        where: OpenWebNet bus address (e.g. '12', '21#4#1').
        dimmable: True if light is dimmable (platform=light).
        transition: Default transition speed 1-10 (platform=light).
        run_time: Full travel runtime in seconds (platform=cover).
        heat_support: Enable heating capability (platform=climate).
        cool_support: Enable cooling capability (platform=climate).
        sensor_type: Type of sensor measurement ('power', 'energy', 'temperature') (platform=sensor).
    """
    try:
        generator = _get_generator()
        kwargs: dict[str, Any] = {
            "dimmable": dimmable,
            "heat_support": heat_support,
            "cool_support": cool_support,
            "type": sensor_type,
        }
        if transition is not None:
            kwargs["transition"] = transition
        if run_time is not None:
            kwargs["run_time"] = run_time

        return generator.generate_ha_yaml(platform=platform, name=name, where=where, **kwargs)
    except Exception as err:
        logger.error("draft_ha_config failed: %s", err, exc_info=True)
        return f"**Error**: {err}"


# ── 9. Get Code Signature / Introspection ────────────────────────────
@mcp.tool()
async def get_code_signature(symbol: str) -> str:
    """Inspect Python AST signatures, public methods, and docstrings from custom_components/myhome or OWNd.

    Args:
        symbol: Class or module name (e.g. 'MyHOMELight', 'MyHOMECover', 'MyHOMEClimate', 'OWNMessage').
    """
    key = symbol.strip()

    async def _impl():
        async with _ast_lock:
            ast_idx = _get_ast_indexer()
            return ast_idx.format_symbol_markdown(symbol)

    try:
        return await _ast_cache.get_or_set(key, _impl)
    except Exception as err:
        logger.error("get_code_signature failed: %s", err, exc_info=True)
        return f"**Error**: {err}"


# ── 10. Rescan Documentation & Indexes ───────────────────────────────
@mcp.tool()
async def rescan_documentation() -> str:
    """Flush caches and reload all OpenWebNet specifications, markdown documents, and codebase AST models."""
    try:
        # Clear all in-memory caches
        _doc_search_cache.clear()
        _who_spec_cache.clear()
        _guide_cache.clear()
        _frame_syntax_cache.clear()
        _ast_cache.clear()

        mgr = _get_rescan_manager()
        summary = mgr.rescan()

        lines = [
            "# OpenWebNet Documentation Rescan Complete",
            "",
            f"- **WHO Families Loaded**: `{summary['who_families_loaded']}`",
            f"- **Documentation Sections**: `{summary['doc_sections']['after']}` (delta: `{summary['doc_sections']['delta']}`)",
            f"- **AST Symbols**: `{summary['ast_symbols']['after']}` (delta: `{summary['ast_symbols']['delta']}`)",
            f"- **Status**: `{summary['status']}`",
        ]
        return "\n".join(lines)
    except Exception as err:
        logger.error("rescan_documentation failed: %s", err, exc_info=True)
        return f"**Error**: {err}"


# ── Resources ────────────────────────────────────────────────────────
@mcp.resource("spec://who-catalog")
async def resource_who_catalog() -> str:
    """Read-only catalog of all OpenWebNet WHO families."""
    catalog = _get_catalog()
    return catalog.format_summary_markdown()


@mcp.resource("spec://protocol-grammar")
async def resource_protocol_grammar() -> str:
    """Read-only OpenWebNet formal grammar and frame templates."""
    grammar_path = get_protocol_grammar_path()
    if grammar_path.exists():
        return grammar_path.read_text(encoding="utf-8")
    return json.dumps({"error": "Grammar file not found"})


@mcp.resource("docs://toc")
async def resource_docs_toc() -> str:
    """Read-only table of contents for OpenWebNet & MyHOME documentation."""
    indexer = _get_doc_indexer()
    return indexer.get_table_of_contents()


@mcp.resource("docs://guide/{topic}")
async def resource_guide(topic: str) -> str:
    """Read-only full text of a documentation guide."""
    indexer = _get_doc_indexer()
    guide = indexer.get_guide(topic)
    if guide:
        return guide
    return f"Guide '{topic}' not found."


# ── CLI Entrypoint ───────────────────────────────────────────────────
def main():
    """Main CLI entrypoint for openwebnet-mcp."""
    # Restore stdout for MCP JSON-RPC protocol
    sys.stdout = os.fdopen(_real_stdout_fd, "w", encoding="utf-8", closefd=False)
    mcp.run()


if __name__ == "__main__":
    main()
