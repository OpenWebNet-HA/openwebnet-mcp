"""AST-driven codebase introspector for MyHOME and OWNd Python sources."""

from __future__ import annotations

import ast
import logging
import os
from pathlib import Path
from typing import Any

from openwebnet_mcp._paths import get_myhome_repo_path, get_ownd_repo_path

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
            "is_valid_message": "@property is_valid_message -> bool",
            "raw": "@property raw -> str",
            "who": "@property who -> int | None",
            "what": "@property what -> int | None",
            "where": "@property where -> str | None",
            "dimension": "@property dimension -> int | None",
        },
        "supported_features": [],
    },
}


_SENTINEL = object()


class AstIndexer:
    """Introspects Python AST from MyHOME and OWNd repositories or falls back to built-in models."""

    def __init__(
        self,
        repo_path: Path | None | object = _SENTINEL,
        ownd_path: Path | None | object = _SENTINEL,
    ) -> None:
        if repo_path is _SENTINEL:
            self.repo_path = get_myhome_repo_path()
        else:
            self.repo_path = repo_path

        if ownd_path is _SENTINEL:
            self.ownd_path = get_ownd_repo_path()
        else:
            self.ownd_path = ownd_path

        self._cache: dict[str, dict[str, Any]] = {}
        self.reindex()

    def reindex(self) -> int:
        """Parse AST of Python modules in repo if present, seeded with built-in reference."""
        self._cache.clear()
        self._cache.update(_BUILTIN_REFERENCE)

        # 1. Parse custom_components/myhome in MyHOME repository
        if self.repo_path and self.repo_path.exists():
            try:
                custom_comp = self.repo_path / "custom_components" / "myhome"
                if custom_comp.exists():
                    for py_file in self._safe_find_py_files(custom_comp):
                        self._parse_py_file(py_file, base_dir=self.repo_path)
            except Exception as err:
                logger.warning("Error indexing MyHOME repo: %s", err)

        # 2. Parse OWNd library repository
        if self.ownd_path and self.ownd_path.exists():
            try:
                ownd_pkg = self.ownd_path / "OWNd"
                src_dir = ownd_pkg if ownd_pkg.exists() else self.ownd_path
                for py_file in self._safe_find_py_files(src_dir):
                    self._parse_py_file(py_file, base_dir=self.ownd_path)
            except Exception as err:
                logger.warning("Error indexing OWNd repo: %s", err)

        logger.info("AST indexer loaded %d symbols across repositories", len(self._cache))
        return len(self._cache)

    def _safe_find_py_files(self, dir_path: Path) -> list[Path]:
        """Safely find python files avoiding broken symlinks, build directories, and caches."""
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
                            "node_modules", "__pycache__", "htmlcov"
                        )
                    )
                ]
                for f in sorted(files):
                    if f.endswith(".py"):
                        found.append(Path(root) / f)
        except Exception as err:
            logger.debug("Error traversing python files in %s: %s", dir_path, err)
        return found

    def _parse_py_file(self, file_path: Path, base_dir: Path | None = None) -> None:
        try:
            code = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(code, filename=str(file_path))
        except Exception as err:
            logger.debug("Failed to parse %s: %s", file_path, err)
            return

        ref_dir = base_dir or (self.repo_path if self.repo_path and self.repo_path.exists() else file_path.parent)
        try:
            rel_parts = file_path.relative_to(ref_dir).parts
            mod_name = ".".join(rel_parts)
            if mod_name.endswith(".py"):
                mod_name = mod_name[:-3]
        except ValueError:
            mod_name = file_path.stem

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                full_name = f"{mod_name}.{node.name}"
                methods: dict[str, str] = {}
                doc = ast.get_docstring(node) or ""

                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
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
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                full_name = f"{mod_name}.{node.name}"
                sig = self._format_signature(node)
                doc = ast.get_docstring(node) or ""
                self._cache[full_name] = {
                    "class_name": node.name,
                    "module": mod_name,
                    "docstring": doc,
                    "methods": {node.name: sig},
                    "supported_features": [],
                    "file_path": str(file_path),
                }

    def _format_signature(self, func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """Format an AST function node into a precise, readable Python signature string."""
        is_prop = any(isinstance(d, ast.Name) and d.id == "property" for d in func_node.decorator_list)
        prefix = "@property " if is_prop else ("async def " if isinstance(func_node, ast.AsyncFunctionDef) else "def ")

        posonly = func_node.args.posonlyargs
        args = func_node.args.args
        defaults = func_node.args.defaults

        total_pos = posonly + args
        num_defaults = len(defaults)
        pos_defaults = [None] * (len(total_pos) - num_defaults) + list(defaults)

        posonly_strs = []
        for a, d in zip(posonly, pos_defaults[: len(posonly)]):
            s = a.arg
            if a.annotation:
                try:
                    s += ": " + ast.unparse(a.annotation)
                except Exception:
                    pass
            if d is not None:
                try:
                    s += "=" + ast.unparse(d)
                except Exception:
                    pass
            posonly_strs.append(s)

        arg_strs = []
        for a, d in zip(args, pos_defaults[len(posonly) :]):
            s = a.arg
            if a.annotation:
                try:
                    s += ": " + ast.unparse(a.annotation)
                except Exception:
                    pass
            if d is not None:
                try:
                    s += "=" + ast.unparse(d)
                except Exception:
                    pass
            arg_strs.append(s)

        all_chunks = []
        if posonly_strs:
            all_chunks.extend(posonly_strs)
            all_chunks.append("/")
        all_chunks.extend(arg_strs)

        if func_node.args.vararg:
            v_str = "*" + func_node.args.vararg.arg
            if func_node.args.vararg.annotation:
                try:
                    v_str += ": " + ast.unparse(func_node.args.vararg.annotation)
                except Exception:
                    pass
            all_chunks.append(v_str)
        elif func_node.args.kwonlyargs:
            all_chunks.append("*")

        for a, d in zip(func_node.args.kwonlyargs, func_node.args.kw_defaults):
            s = a.arg
            if a.annotation:
                try:
                    s += ": " + ast.unparse(a.annotation)
                except Exception:
                    pass
            if d is not None:
                try:
                    s += "=" + ast.unparse(d)
                except Exception:
                    pass
            all_chunks.append(s)

        if func_node.args.kwarg:
            k_str = "**" + func_node.args.kwarg.arg
            if func_node.args.kwarg.annotation:
                try:
                    k_str += ": " + ast.unparse(func_node.args.kwarg.annotation)
                except Exception:
                    pass
            all_chunks.append(k_str)

        ret = ""
        if func_node.returns:
            try:
                ret = " -> " + ast.unparse(func_node.returns)
            except Exception:
                pass

        if is_prop:
            return f"@property {func_node.name}{ret}"
        joined_args = ", ".join(all_chunks)
        return f"{prefix}{func_node.name}({joined_args}){ret}"

    def get_symbol(self, query: str) -> dict[str, Any] | None:
        """Find symbol by full name, class name, function name, or Class.method."""
        q = query.strip()
        if not q:
            return None

        if q in self._cache:
            return self._cache[q]

        for k, v in self._cache.items():
            if k.endswith("." + q) or v.get("class_name", "").lower() == q.lower():
                return v

        # Support Class.method syntax (e.g. MyHOMELight.async_turn_on)
        if "." in q:
            parts = q.split(".")
            class_name = parts[-2]
            method_name = parts[-1]
            parent = self.get_symbol(class_name)
            if parent and method_name in parent.get("methods", {}):
                return {
                    "class_name": f"{parent.get('class_name')}.{method_name}",
                    "module": parent.get("module", ""),
                    "docstring": f"Method `{method_name}` of `{parent.get('class_name')}`.",
                    "methods": {method_name: parent["methods"][method_name]},
                    "supported_features": parent.get("supported_features", []),
                    "file_path": parent.get("file_path", ""),
                }

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
