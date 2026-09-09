# OpenWebNet-MCP Server

[![CI Pipeline](https://github.com/OpenWebNet-HA/openwebnet-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/OpenWebNet-HA/openwebnet-mcp/actions/workflows/ci.yml)
[![Platform Validation](https://img.shields.io/badge/Platforms-Windows%20%7C%20macOS%20%7C%20Linux-success?logo=githubactions)](https://github.com/OpenWebNet-HA/openwebnet-mcp/actions/workflows/ci.yml)
[![Python Support](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue?logo=python)](https://github.com/OpenWebNet-HA/openwebnet-mcp/actions/workflows/ci.yml)
![License](https://img.shields.io/badge/License-MIT-green.svg)

> **Empower AI Agents to Browse, Understand, and Generate OpenWebNet Protocol & Home Assistant MyHOME Automations.**
> Zero hallucinations: Built directly from official BTicino/Legrand technical specifications, community manuals, and production Home Assistant integration source code.

`openwebnet-mcp` is an asynchronous, Model Context Protocol (MCP) server built with Python 3.11+ using the official `FastMCP` framework. It provides AI agents (Claude Desktop, Cursor, VS Code, Antigravity) with immediate, deep semantic context over the entire OpenWebNet protocol, 20+ WHO specification families, frame validation grammar, and Home Assistant `myhome` custom component architecture.

---

## 🚀 Quick Start

### 1. Add to your MCP Client Configuration

#### Claude Desktop / Cursor / VS Code (`mcp.json`):
```json
{
  "mcpServers": {
    "openwebnet-mcp": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/OpenWebNet-HA/openwebnet-mcp.git", "openwebnet-mcp"]
    }
  }
}
```

#### Local Development Run (using uv or virtualenv):
```json
{
  "mcpServers": {
    "openwebnet-mcp": {
      "command": "python",
      "args": ["-m", "openwebnet_mcp.server"],
      "cwd": "C:\\Users\\laurensvdb\\Documents\\GitHub\\openwebnet-mcp"
    }
  }
}
```

---

## 🤖 Agentic Interaction Examples

Once connected, your AI coding assistant can browse documentation, interpret frames, and generate verified code autonomously.

### Example 1: Decode a Bus Monitor Frame
**User Prompt:**
> "I saw this frame on my SCS bus trace: `*#4*1*#14*0215*1##`. What does it mean and which hardware is involved?"

**AI Agent Action:**
1. Calls `parse_and_validate_frame("*#4*1*#14*0215*1##")`.
2. Resolves WHO=4 (Heating/Thermoregulation), Dimension 14 (Target Temperature & Mode), Zone 1, Target 21.5°C, Mode 1 (Heating).
3. Returns human-readable breakdown and lists compatible thermostat units (3550, L4691).

### Example 2: Configure CEN+ Scenario Pushbuttons
**User Prompt:**
> "How do I configure my BTicino 3477 CEN+ interface to toggle a light when button 2 is pressed, and what OpenWebNet frames are sent?"

**AI Agent Action:**
1. Calls `get_ha_guide("cen_scenarios")` to review the CEN vs CEN+ specifications and Home Assistant blueprint.
2. Calls `draft_own_frame(who=25, command_type="command", where="11", what="21#2")` to show the short-press pulse frame `*25*21#2*11##`.
3. Calls `draft_ha_config(platform="light", ...)` to draft the complete automation YAML.

### Example 3: Solve Light Transition Inconsistencies
**User Prompt:**
> "My dimmable lights jump instantly to brightness instead of ramping smoothly when I pass `transition: 5`. Why?"

**AI Agent Action:**
1. Calls `search_documentation("transition stepped dimming")`.
2. Reads the technical design document explaining hardware ramp limitations in older F411/F418 actuators vs software-emulated stepped dimming.
3. Suggests the proper configuration and command sequence.

---

## 🛠️ Tools & Resources Reference

### MCP Tools (10)

| Tool | Description |
|---|---|
| `search_documentation` | Ranked keyword and fuzzy search across all protocol specs, guides, and design docs. |
| `get_who_spec` | Retrieve full technical specification, WHAT commands, and DIMENSIONS for a WHO family. |
| `list_who_catalog` | Summary inventory table of all 20+ OpenWebNet WHO families with archive status. |
| `get_ha_guide` | Full markdown guide for configuring and troubleshooting Home Assistant MyHOME platforms. |
| `lookup_frame_syntax` | Grammar, regex templates, and parameter formats for OpenWebNet message types. |
| `parse_and_validate_frame` | Deep syntax and semantic validation of any raw OpenWebNet frame string. |
| `draft_own_frame` | Construct and validate a syntactically correct OpenWebNet frame string. |
| `draft_ha_config` | Generate production-ready Home Assistant configuration YAML for MyHOME entities. |
| `get_code_signature` | Inspect Python AST signatures and docstrings from `custom_components/myhome` or `OWNd`. |
| `rescan_documentation` | Flush caches and reload all OpenWebNet specifications, documents, and AST models. |

### MCP Resources (4)

| URI | Description |
|---|---|
| `spec://who-catalog` | Read-only catalog of all OpenWebNet WHO families. |
| `spec://protocol-grammar` | Read-only formal OpenWebNet grammar, regex patterns, and session specs. |
| `docs://toc` | Master Table of Contents for all indexed OpenWebNet & MyHOME documentation. |
| `docs://guide/{topic}` | Read-only full text of a specific documentation guide. |

---

## 📚 Master WHO Family Inventory

| WHO | Subsystem | Official Title | Status | HA Platform |
|:---:|:---|:---|:---:|:---|
| **0** | Scenarios (Basic) | `WHO_0.pdf` | 🟢 Archived | `event` |
| **1** | Lighting | `WHO_1.pdf` | 🟢 Archived | `light` |
| **2** | Automation (Covers) | `WHO_2.pdf` | 🟢 Archived | `cover` |
| **3** | Load Control | `WHO_3.pdf` | 🟡 Legacy | `switch`, `sensor` |
| **4** | Thermoregulation | `WHO_4 2.pdf` | 🟢 Archived | `climate`, `sensor` |
| **5** | Burglar Alarm | `WHO_5.pdf` | 🟢 Archived | `alarm_control_panel` |
| **6** | Door Entry Call & Lock | `WHO_6.pdf` | 🟡 Legacy | `lock`, `event` |
| **7** | Video Door Entry | `WHO_7.pdf` | 🟢 Archived | `camera` |
| **9** | Auxiliary | `WHO_9.pdf` | 🟡 Legacy | `switch` |
| **13** | Gateway Management | `WHO_13.pdf` | 🟢 Archived | Diagnostics |
| **14** | Actuators & Lock | `WHO_14.pdf` | 🔴 Needed | Diagnostics |
| **15** | CEN Pushbuttons | `WHO_15.pdf` | 🟢 Archived | `event` |
| **16** | Sound System | `WHO_16.pdf` | 🟢 Archived | `media_player` |
| **17** | MH200N Scenarios | `WHO_17.pdf` | 🟢 Archived | `event` |
| **18** | Energy Management | `WHO_18.pdf` | 🟢 Archived | `sensor` |
| **22** | Sound Diffusion (Ext) | `WHO_22.pdf` | 🟢 Archived | `media_player` |
| **24** | Lighting / DALI | `WHO_24.pdf` | 🟢 Archived | `light` |
| **25** | CEN+ / Dry Contacts | `WHO_25.pdf` | 🟢 Archived | `event`, `binary_sensor` |
| **1001** | Bus Diagnostics | `WHO_1001.pdf` | 🟢 Archived | Diagnostics |
| **1004** | Heating Diagnostics | `WHO_1004.pdf` | 🟢 Archived | Diagnostics |
| **1013** | Gateway Diagnostics| `WHO_1013.pdf` | 🟢 Archived | Diagnostics |

---

## 🧪 Testing

Run unit tests and verify coverage with `pytest`:

```bash
pip install -e ".[dev]"
pytest --cov=src/openwebnet_mcp --cov-report=term-missing
```

---

## 📄 License

MIT License. Copyright (c) 2026 OpenWebNet-HA Community.
