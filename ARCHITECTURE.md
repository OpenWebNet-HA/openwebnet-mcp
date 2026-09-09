# OpenWebNet-MCP Technical Architecture

## 1. System Overview

`openwebnet-mcp` is an asynchronous Model Context Protocol (MCP) server built with Python 3.11+ using the official `FastMCP` framework. It serves as a definitive knowledge engine, frame syntax validator, and Home Assistant configuration generator for the BTicino/Legrand OpenWebNet protocol and `MyHOME` custom component integration.

The server operates over standard input/output (stdio) using the JSON-RPC 2.0 protocol.

---

## 2. Core Architectural Pillars

### 2.1 Stdio Protection & Real-time Logging
Because JSON-RPC 2.0 uses standard input and standard output, stray `print()` calls or warnings from external libraries can corrupt the communication pipe.
- At initialization, `server.py` duplicates file descriptor 1 (`os.dup(sys.stdout.fileno())`) and redirects Python-level `sys.stdout` to `sys.stderr`.
- When `main()` invokes `mcp.run()`, `sys.stdout` is restored from the saved descriptor, guaranteeing a clean stdio transport.
- A custom `FlushingFileHandler` with `os.fsync()` streams logs directly to disk without OS chunking delays, enabling real-time inspection via `startup.log`.

### 2.2 Semantic Documentation Indexer (`doc_indexer.py`)
- Ingests embedded markdown documentation guides covering the OpenWebNet WHO catalog, lighting, covers, climate, CEN/CEN+ pushbuttons, energy management, sound systems, and software stepped dimming.
- Chunks text by markdown headings and builds an in-memory index with token matching, ranked term frequency, and fuzzy similarity using `difflib.SequenceMatcher`.
- Generates contextual snippets around search matches to minimize LLM token usage while maximizing information density.

### 2.3 Frame Grammar & Protocol Parser (`frame_parser.py`)
- Employs compiled regular expressions matching all valid OpenWebNet message formats:
  - `STATUS_EVENT`: `*WHO*WHAT*WHERE##`
  - `COMMAND_TRANSLATION`: `*WHO*1000#WHAT*WHERE##`
  - `STATUS_REQUEST`: `*#WHO*WHERE##`
  - `DIMENSION_REQUEST`: `*#WHO*WHERE*DIMENSION##`
  - `DIMENSION_WRITING`: `*#WHO*WHERE*#DIMENSION*VAL1*...*VALn##`
  - `DIMENSION_REPLY`: `*#WHO*WHERE*DIMENSION*VAL1*...*VALn##`
  - Session and handshake frames (`*99*0##`, `*99*1##`, `*#*1##`, `*#*0##`).
- Cross-references parsed frames against the WHO specification catalog to validate whether the WHO family exists, whether the WHAT command is recognized, and whether dimension parameters are valid.
- Translates raw frames into natural language explanations.

### 2.4 Codebase AST Introspection (`ast_indexer.py`)
- Performs static Abstract Syntax Tree (AST) analysis on Python source files in `custom_components/myhome` and `OWNd` without executing arbitrary code.
- Extracts class hierarchies, method signatures, parameter type annotations, docstrings, and supported entity features.
- Contains built-in fallback reference models for all core platform classes (`MyHOMELight`, `MyHOMECover`, `MyHOMEClimate`, `OWNMessage`), ensuring full functionality in standalone environments.

### 2.5 In-Memory Asynchronous TTL Caching
- Eliminates redundant string parsing and document searching across repeated agent queries using `AsyncTTLCache`.
- Supports configurable TTL (default 10 minutes), LRU capacity eviction, and active expired key purging.

---

## 3. Directory Layout

```
openwebnet-mcp/
├── .github/
│   └── workflows/
│       └── ci.yml               # Multi-OS (Ubuntu, macOS, Windows) & Python (3.11-3.14) CI
├── .gitignore
├── LICENSE                      # MIT License
├── README.md                    # Quick start, agentic examples, tools reference
├── ARCHITECTURE.md              # Detailed technical design
├── pyproject.toml               # Hatchling build metadata & dependencies
├── run_server.cmd               # Windows batch launcher
├── run_server.sh                # Unix bash launcher
├── src/
│   └── openwebnet_mcp/
│       ├── __init__.py          # Version & exports
│       ├── _paths.py            # Path resolution & env overrides
│       ├── who_catalog.py       # OpenWebNet WHO catalog & specification provider
│       ├── frame_parser.py      # Frame grammar parser & semantic validator
│       ├── frame_generator.py   # Frame builder & HA YAML generator
│       ├── doc_indexer.py       # Documentation chunker & ranked search
│       ├── ast_indexer.py       # Static AST codebase introspection
│       ├── rescan_manager.py   # Cache buster & index reloader
│       ├── server.py            # FastMCP JSON-RPC server
│       └── data/
│           ├── who_catalog.json # Catalog of 21 WHO families
│           ├── protocol_grammar.json # Formal OpenWebNet syntax rules
│           └── docs/            # Markdown guides for all subsystems
└── tests/                       # Complete pytest suite (95%+ coverage)
```
