"""OpenWebNet WHO Catalog and Specification Provider."""

from __future__ import annotations

import difflib
import json
import logging
from pathlib import Path
from typing import Any

from openwebnet_mcp._paths import get_who_catalog_path

logger = logging.getLogger("openwebnet_mcp.who_catalog")


class WhoCatalog:
    """Provides querying and fuzzy search over the OpenWebNet WHO catalog."""

    def __init__(self, catalog_path: Path | None = None) -> None:
        self.catalog_path = catalog_path or get_who_catalog_path()
        self._families: dict[int, dict[str, Any]] = {}
        self._load_catalog()

    def _load_catalog(self) -> None:
        if not self.catalog_path.exists():
            logger.warning("WHO catalog not found at %s", self.catalog_path)
            return

        try:
            data = json.loads(self.catalog_path.read_text(encoding="utf-8"))
            for entry in data.get("families", []):
                who_id = int(entry.get("who"))
                self._families[who_id] = entry
            logger.info("Loaded %d WHO families from catalog", len(self._families))
        except Exception as err:
            logger.error("Failed to load WHO catalog: %s", err)
            raise

    def get_family(self, who: int) -> dict[str, Any] | None:
        """Get WHO specification by integer ID."""
        return self._families.get(int(who))

    def list_all(self) -> list[dict[str, Any]]:
        """Return all catalog entries sorted by WHO id."""
        return sorted(self._families.values(), key=lambda x: x["who"])

    def search(self, query: str) -> list[dict[str, Any]]:
        """Fuzzy and keyword search across WHO specifications."""
        q = query.strip().lower()
        if not q:
            return self.list_all()

        results: list[tuple[float, dict[str, Any]]] = []
        for entry in self._families.values():
            score = 0.0
            who_str = str(entry.get("who", ""))
            name = entry.get("name", "").lower()
            it_name = entry.get("italian_name", "").lower()
            desc = entry.get("description", "").lower()
            ha_plat = entry.get("ha_platform", "").lower()
            models = " ".join(entry.get("hardware_models", [])).lower()

            # Exact WHO match
            clean_q = q.replace("who=", "").replace("who", "").strip()
            if clean_q == who_str or q == who_str:
                score += 10.0

            # Substring matches
            if q in name:
                score += 5.0
            if q in it_name:
                score += 4.0
            if q in ha_plat:
                score += 4.0
            if q in desc:
                score += 2.0
            if q in models:
                score += 2.0

            # Fuzzy name similarity
            ratio = difflib.SequenceMatcher(None, q, name).ratio()
            if ratio > 0.6:
                score += ratio * 3.0

            if score > 0:
                results.append((score, entry))

        results.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in results]

    def format_summary_markdown(self) -> str:
        """Format an inventory markdown table of all WHO families."""
        lines = [
            "# OpenWebNet Master WHO Catalog",
            "",
            "| WHO | Subsystem | Official Title | Status | Home Assistant Entity |",
            "|:---:|:---|:---|:---:|:---|",
        ]
        for f in self.list_all():
            who = f.get("who")
            name = f.get("name")
            doc = f.get("document_title", "-")
            status = f.get("status", "Unknown")
            ha = f.get("ha_platform", "-")
            lines.append(f"| **{who}** | {name} | `{doc}` | {status} | `{ha}` |")

        return "\n".join(lines)

    def format_family_details(self, who: int) -> str:
        """Render complete markdown specification for a single WHO family."""
        f = self.get_family(who)
        if not f:
            return f"**Error**: WHO family `{who}` is not recognized in the OpenWebNet catalog."

        lines = [
            f"# WHO = {f.get('who')}: {f.get('name')} ({f.get('italian_name', '')})",
            "",
            f"- **Official Document**: {f.get('document_title')} (`{f.get('pdf_filename')}`)",
            f"- **Version / Date**: {f.get('version')} ({f.get('date')})",
            f"- **Archive Status**: {f.get('status')}",
            f"- **Home Assistant Platform**: `{f.get('ha_platform')}`",
            f"- **Hardware Modules**: {', '.join(f.get('hardware_models', []))}",
            "",
            "## Description",
            f.get("description", ""),
            "",
            "## Addressing Scheme (`WHERE`)",
            f.get("addressing", ""),
            "",
            "## WHAT Commands",
        ]

        whats = f.get("what_commands", {})
        if whats:
            lines.extend([
                "| WHAT Code | Description / Action |",
                "|:---|:---|",
            ])
            for code, desc in whats.items():
                lines.append(f"| `{code}` | {desc} |")
        else:
            lines.append("*(No standard WHAT commands; uses DIMENSIONS or diagnostic frames)*")

        lines.extend(["", "## DIMENSIONS"])
        dims = f.get("dimensions", {})
        if dims:
            for dim_id, d in dims.items():
                lines.append(f"### Dimension {dim_id}: {d.get('name')}")
                lines.append(f"{d.get('description')}")
                if d.get("query"):
                    lines.append(f"- **Query**: `{d.get('query')}`")
                if d.get("write"):
                    lines.append(f"- **Write**: `{d.get('write')}`")
                lines.append("")
        else:
            lines.append("*(No dimension parameters defined for this family)*")

        lines.extend(["", "## Example Frames"])
        examples = f.get("examples", [])
        if examples:
            for ex in examples:
                lines.append(f"- `{ex.get('frame')}`: {ex.get('description')}")
        else:
            lines.append("*(No examples provided)*")

        return "\n".join(lines)
