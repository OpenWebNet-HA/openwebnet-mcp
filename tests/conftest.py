"""Pytest fixtures and configuration for openwebnet-mcp."""

import pytest
import os
from pathlib import Path

from openwebnet_mcp import server


@pytest.fixture(autouse=True)
def reset_server_state():
    """Reset server singletons and caches between tests."""
    server._catalog = None
    server._parser = None
    server._generator = None
    server._doc_indexer = None
    server._ast_indexer = None
    server._rescan_manager = None

    server._doc_search_cache.clear()
    server._who_spec_cache.clear()
    server._guide_cache.clear()
    server._frame_syntax_cache.clear()
    server._ast_cache.clear()
