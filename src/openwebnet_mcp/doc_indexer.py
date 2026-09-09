"""Documentation indexer and semantic search engine for OpenWebNet & MyHOME."""

from __future__ import annotations

import difflib
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openwebnet_mcp._paths import get_embedded_docs_dir, get_external_docs_paths

logger = logging.getLogger("openwebnet_mcp.doc_indexer")


@dataclass
class DocSection:
    """Represents an indexed section of a documentation file."""

    doc_name: str
    file_path: str
    category: str
    heading: str
    level: int
    content: str
    tokens: set[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_name": self.doc_name,
            "file_path": self.file_path,
            "category": self.category,
            "heading": self.heading,
            "level": self.level,
            "content": self.content,
        }


class DocIndexer:
    """Parses and indexes OpenWebNet documentation for fast search and browsing."""

    def __init__(
        self,
        embedded_docs_dir: Path | None = None,
        external_paths: list[Path] | None = None,
    ) -> None:
        self.embedded_docs_dir = embedded_docs_dir or get_embedded_docs_dir()
        self.external_paths = external_paths if external_paths is not None else get_external_docs_paths()
        self.sections: list[DocSection] = []
        self.docs_by_topic: dict[str, str] = {}
        self.category_by_topic: dict[str, str] = {}
        self.reindex()

    def reindex(self) -> int:
        """Scan all documentation locations and rebuild in-memory search index."""
        self.sections.clear()
        self.docs_by_topic.clear()
        self.category_by_topic.clear()
        self._seen_files: set[str] = set()

        # 1. Index embedded documentation (primary source of truth)
        if self.embedded_docs_dir.exists():
            for md_file in sorted(self.embedded_docs_dir.glob("*.md")):
                self._index_file(md_file, category="embedded_guide")

        # 2. Index external documentation directories (if present on local filesystem)
        for ext_path in self.external_paths:
            if not ext_path.exists():
                continue
            if ext_path.is_file() and ext_path.suffix.lower() in (".md", ".markdown", ".txt"):
                self._index_file(ext_path, category="external_reference")
            elif ext_path.is_dir():
                for doc_file in self._safe_find_files(ext_path):
                    self._index_file(doc_file, category="external_reference")

        logger.info("Indexed %d document sections across %d unique files", len(self.sections), len(self.docs_by_topic))
        return len(self.sections)

    def _safe_find_files(self, dir_path: Path) -> list[Path]:
        """Safely find markdown and text files avoiding broken symlinks, venvs, and build folders."""
        found: list[Path] = []
        try:
            for root, dirs, files in os.walk(str(dir_path), followlinks=False):
                dirs[:] = [
                    d for d in dirs
                    if not (
                        d.startswith(".")
                        or d.endswith(".egg-info")
                        or d.lower() in (
                            "venv", "env", ".venv", "lib64", "build", "dist",
                            "node_modules", "__pycache__", "htmlcov", "openhab-addons"
                        )
                    )
                ]
                for f in sorted(files):
                    f_lower = f.lower()
                    if f.startswith("_"):
                        continue
                    if f_lower.endswith((".md", ".markdown")) or f_lower == "who16_doc.txt":
                        found.append(Path(root) / f)
        except Exception as err:
            logger.debug("Error traversing %s: %s", dir_path, err)
        return found

    def _index_file(self, file_path: Path, category: str) -> None:
        try:
            resolved_key = str(file_path.resolve())
        except Exception:
            resolved_key = str(file_path)

        if hasattr(self, "_seen_files") and resolved_key in self._seen_files:
            return
        if hasattr(self, "_seen_files"):
            self._seen_files.add(resolved_key)

        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as err:
            logger.warning("Could not read doc file %s: %s", file_path, err)
            return

        stem = file_path.stem.lower().replace("-", "_")
        self.docs_by_topic[stem] = text
        self.category_by_topic[stem] = category

        # Parse sections by headers (#, ##, ###)
        current_heading = file_path.stem.replace("-", " ").replace("_", " ").title()
        current_level = 1
        current_lines: list[str] = []

        header_re = re.compile(r"^(#{1,4})\s+(.+)$")

        for line in text.splitlines():
            m = header_re.match(line)
            if m:
                # Flush previous section
                if current_lines:
                    content = "\n".join(current_lines).strip()
                    if content:
                        self.sections.append(
                            DocSection(
                                doc_name=file_path.name,
                                file_path=str(file_path),
                                category=category,
                                heading=current_heading,
                                level=current_level,
                                content=content,
                                tokens=self._tokenize(current_heading + " " + content),
                            )
                        )
                current_level = len(m.group(1))
                current_heading = m.group(2).strip()
                current_lines = [line]
            else:
                current_lines.append(line)

        # Flush final section
        if current_lines:
            content = "\n".join(current_lines).strip()
            if content:
                self.sections.append(
                    DocSection(
                        doc_name=file_path.name,
                        file_path=str(file_path),
                        category=category,
                        heading=current_heading,
                        level=current_level,
                        content=content,
                        tokens=self._tokenize(current_heading + " " + content),
                    )
                )

    def search(self, query: str, category: str | None = None, limit: int = 8) -> list[dict[str, Any]]:
        """Search documentation using ranked token matching and difflib similarity."""
        q = query.strip().lower()
        if not q:
            # Return first few sections with full metadata expected by callers
            output: list[dict[str, Any]] = []
            for sec in self.sections[:limit]:
                d = sec.to_dict()
                d["relevance_score"] = 0.0
                d["snippet"] = self._create_snippet(sec.content, "")
                output.append(d)
            return output

        query_tokens = self._tokenize(q)
        results: list[tuple[float, DocSection]] = []

        for sec in self.sections:
            if category and category.lower() not in sec.category.lower():
                continue

            score = 0.0
            heading_lower = sec.heading.lower()
            content_lower = sec.content.lower()

            # Exact phrase matches
            if q in heading_lower:
                score += 15.0
            if q in content_lower:
                score += 6.0

            # Token overlap
            token_overlap = query_tokens.intersection(sec.tokens)
            score += len(token_overlap) * 3.0

            # Heading fuzzy similarity
            ratio = difflib.SequenceMatcher(None, q, heading_lower).ratio()
            if ratio > 0.5:
                score += ratio * 8.0

            if score > 0:
                results.append((score, sec))

        results.sort(key=lambda x: x[0], reverse=True)
        top = results[:limit]

        output: list[dict[str, Any]] = []
        for score, sec in top:
            d = sec.to_dict()
            d["relevance_score"] = round(score, 2)
            d["snippet"] = self._create_snippet(sec.content, q)
            output.append(d)

        return output

    def get_guide(self, topic: str) -> str | None:
        """Get the full text of a guide by topic keyword."""
        t = topic.lower().strip().replace("-", "_")
        # 1. Direct match
        if t in self.docs_by_topic:
            return self.docs_by_topic[t]

        # 2. Canonical guide suffixes (e.g. "lighting" -> "lighting_guide", "light" -> "lighting_guide")
        for candidate in (f"{t}_guide", f"{t}ing_guide", f"{t}s_guide", f"{t}_configuration", f"{t}s_configuration"):
            if candidate in self.docs_by_topic:
                return self.docs_by_topic[candidate]

        # 3. Substring match prioritizing keys that start with query or have higher similarity
        matching_keys = [k for k in self.docs_by_topic if t in k or k in t]
        if matching_keys:
            matching_keys.sort(
                key=lambda k: (
                    k.startswith(t),
                    difflib.SequenceMatcher(None, t, k).ratio(),
                    -abs(len(k) - len(t)),
                ),
                reverse=True,
            )
            return self.docs_by_topic[matching_keys[0]]

        # 4. Fuzzy match
        keys = list(self.docs_by_topic.keys())
        matches = difflib.get_close_matches(t, keys, n=1, cutoff=0.5)
        if matches:
            return self.docs_by_topic[matches[0]]

        return None

    def get_table_of_contents(self) -> str:
        """Render a table of contents for all indexed documents."""
        lines = [
            "# OpenWebNet & MyHOME Documentation Table of Contents",
            "",
            f"Total indexed sections: {len(self.sections)} across {len(self.docs_by_topic)} documents.",
            "",
            "## Embedded Guides & Architectural References",
        ]
        embedded = [t for t in sorted(self.docs_by_topic.keys()) if self.category_by_topic.get(t) == "embedded_guide"]
        for topic in embedded:
            title = topic.replace("_", " ").title()
            lines.append(f"- **`{topic}`**: {title}")

        external = [t for t in sorted(self.docs_by_topic.keys()) if self.category_by_topic.get(t) != "embedded_guide"]
        if external:
            lines.extend([
                "",
                "## External Wiki & Community Specifications",
            ])
            for topic in external:
                title = topic.replace("_", " ").title()
                lines.append(f"- **`{topic}`**: {title}")

        lines.extend([
            "",
            "## Key Sections",
        ])
        seen = set()
        for sec in self.sections:
            key = (sec.doc_name, sec.heading)
            if key not in seen:
                seen.add(key)
                indent = "  " * (sec.level - 1)
                lines.append(f"{indent}- {sec.heading} (`{sec.doc_name}`)")

        return "\n".join(lines)

    def _tokenize(self, text: str) -> set[str]:
        words = re.findall(r"\w+", text.lower())
        return {w for w in words if len(w) > 2}

    def _create_snippet(self, content: str, query: str, max_chars: int = 350) -> str:
        """Extract a readable snippet highlighting query match."""
        idx = content.lower().find(query.lower())
        if idx == -1:
            return content[:max_chars].strip() + ("..." if len(content) > max_chars else "")

        start = max(0, idx - 100)
        end = min(len(content), idx + max_chars - 100)
        snippet = content[start:end].strip()
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."
        return snippet
