"""AST-driven codebase introspector for MyHOME and OWNd Python sources."""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Any

from openwebnet_mcp._paths import get_myhome_repo_path

logger = logging.getLogger("openwebnet_mcp.ast_indexer")


# Built-in reference signatures for offline / standalone use
_BUILTIN_REFERENCE: dict[str, dict[str, Any]] = {
    "custom_components.myhome.light.MyHOMELight": {
        "class_name": "MyHOMELight",
        "module": "custom_components.myhome.light",
        "docstring": "Representation of a MyHOME OpenWebNet Light entity (relay, dimmer, DALI).",
        "methods": {
            "__init__": "def __init__(self, coordinator, entity_description, where, dimmable=False)",
            "async_turn_on": "async def async_turn_on(self, **kwargs: Any) -> None",
            "async_turn_off": "async def async_turn_off(self, **kwargs: Any) -> None",
            "handle_event": "def handle_event(self, event: OWNEvent) -> None",
        },
        "supported_features": ["LightEntityFeature.TRANSITION (when dimmable)", "ColorMode.BRIGHTNESS", "ColorMode.ONOFF"],
    },
    "custom_components.myhome.cover.MyHOMECover": {
        "class_name": "MyHOMECover",
        "module": "custom_components.myhome.cover",
        "docstring": "Representation of a MyHOME OpenWebNet Cover/Shutter entity.",
        "methods": {
            "__init__": "def __init__(self, coordinator, entity_description, where, run_time=None)",
            "async_open_cover": "async def async_open_cover(self, **kwargs: Any) -> None",
            "async_close_cover": "async def async_close_cover(self, **kwargs: Any) -> None",
            "async_stop_cover": "async def async_stop_cover(self, **kwargs: Any) -> None",
            "async_set_cover_position": "async def async_set_cover_position(self, **kwargs: Any) -> None",
        },
        "supported_features": ["CoverEntityFeature.OPEN", "CoverEntityFeature.CLOSE", "CoverEntityFeature.STOP", "CoverEntityFeature.SET_POSITION"],
    },
    "custom_components.myhome.climate.MyHOMEClimate": {
        "class_name": "MyHOMEClimate",
        "module": "custom_components.myhome.climate",
        "docstring": "Representation of a MyHOME OpenWebNet Climate entity (thermoregulation zone).",
        "methods": {
            "__init__": "def __init__(self, coordinator, entity_description, zone, heat_support=True, cool_support=False)",
            "async_set_hvac_mode": "async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None",
            "async_set_temperature": "async def async_set_temperature(self, **kwargs: Any) -> None",
        },
        "supported_features": ["ClimateEntityFeature.TARGET_TEMPERATURE"],
    },
    "custom_components.myhome.ownd.message.OWNMessage": {
        "class_name": "OWNMessage",
        "module": "custom_components.myhome.ownd.message",
        "docstring": "Base parser and container for all OpenWebNet frames.",
        "methods": {
            "__init__": "def __init__(self, data: str)",
            "is_valid_message": "property is_valid_message -> bool",
            "raw": "property raw -> str",
            "who": "property who -> int | None",
            "what": "property what -> int | None",
            "where": "property where -> str | None",
            "dimension": "property dimension -> int | None",
        },
        "supported_features": [],
    },
}


_SENTINEL = object()


class AstIndexer:
    """Introspects Python AST from MyHOME repository or falls back to built-in models."""

    def __init__(self, repo_path: Path | None | object = _SENTINEL) -> None:
        if repo_path is _SENTINEL:
            self.repo_path = get_myhome_repo_path()
        else:
            self.repo_path = repo_path
        self._cache: dict[str, dict[str, Any]] = {}
        self.reindex()

    def reindex(self) -> int:
        """Parse AST of Python modules in repo if present, seeded with built-in reference."""
        self._cache.clear()
        self._cache.update(_BUILTIN_REFERENCE)

        if not self.repo_path or not self.repo_path.exists():
            logger.info("Local MyHOME repo not found; running with %d built-in AST reference models", len(self._cache))
            return len(self._cache)

        try:
            custom_comp = self.repo_path / "custom_components" / "myhome"
            if custom_comp.exists():
                for py_file in custom_comp.rglob("*.py"):
                    self._parse_py_file(py_file)
            logger.info("AST indexer loaded %d symbols across repository", len(self._cache))
        except Exception as err:
            logger.warning("Error during live AST indexing: %s", err)

        return len(self._cache)

    def _parse_py_file(self, file_path: Path) -> None:
        try:
            code = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(code, filename=str(file_path))
        except Exception as err:
            logger.debug("Failed to parse %s: %s", file_path, err)
            return

        rel_parts = file_path.relative_to(self.repo_path).parts
        mod_name = ".".join(rel_parts)[:-3]  # remove .py

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                full_name = f"{mod_name}.{node.name}"
                methods = {}
                doc = ast.get_docstring(node) or ""
                
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        # Build signature string
                        sig = self._format_signature(item)
                        methods[item.name] = sig

                self._cache[full_name] = {
                    "class_name": node.name,
                    "module": mod_name,
                    "docstring": doc,
                    "methods": methods,
                    "supported_features": [],
                    "file_path": str(file_path),
                }

    def _format_signature(self, func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        prefix = "async def " if isinstance(func_node, ast.AsyncFunctionDef) else "def "
        args = []
        for a in func_node.args.args:
            arg_str = a.arg
            if a.annotation:
                try:
                    arg_str += f": {ast.unparse(a.annotation)}"
                except Exception:
                    pass
            args.append(arg_str)

        if func_node.args.vararg:
            args.append(f"*{func_node.args.vararg.arg}")
        if func_node.args.kwarg:
            kw_str = f"**{func_node.args.kwarg.arg}"
            if func_node.args.kwarg.annotation:
                try:
                    kw_str += f": {ast.unparse(func_node.args.kwarg.annotation)}"
                except Exception:
                    pass
            args.append(kw_str)

        ret = ""
        if func_node.returns:
            try:
                ret = f" -> {ast.unparse(func_node.returns)}"
            except Exception:
                pass

        return f"{prefix}{func_node.name}({', '.join(args)}){ret}"

    def get_symbol(self, query: str) -> dict[str, Any] | None:
        """Find symbol by full name or class name."""
        q = query.strip()
        if q in self._cache:
            return self._cache[q]

        for k, v in self._cache.items():
            if k.endswith("." + q) or v.get("class_name", "").lower() == q.lower():
                return v

        return None

    def format_symbol_markdown(self, query: str) -> str:
        """Format inspected symbol details as markdown."""
        info = self.get_symbol(query)
        if not info:
            return f"**Error**: Symbol '{query}' not found in AST index."

        lines = [
            f"# `{info['class_name']}` ({info['module']})",
            "",
            info.get("docstring", "No docstring provided."),
            "",
            "## Public Methods & Signatures",
        ]

        methods = info.get("methods", {})
        if methods:
            for name, sig in methods.items():
                if not name.startswith("_") or name == "__init__":
                    lines.append(f"- `{sig}`")
        else:
            lines.append("*(No public methods found)*")

        features = info.get("supported_features", [])
        if features:
            lines.extend(["", "## Supported Entity Features"])
            for f in features:
                lines.append(f"- `{f}`")

        return "\n".join(lines)
