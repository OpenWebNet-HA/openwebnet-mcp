"""Rescan manager for refreshing documentation and AST indexes."""

from __future__ import annotations

import logging
from typing import Any

from openwebnet_mcp.ast_indexer import AstIndexer
from openwebnet_mcp.doc_indexer import DocIndexer
from openwebnet_mcp.who_catalog import WhoCatalog

logger = logging.getLogger("openwebnet_mcp.rescan_manager")


class RescanManager:
    """Coordinates re-indexing of documentation, WHO specs, and AST symbols."""

    def __init__(
        self,
        who_catalog: WhoCatalog,
        doc_indexer: DocIndexer,
        ast_indexer: AstIndexer,
    ) -> None:
        self.who_catalog = who_catalog
        self.doc_indexer = doc_indexer
        self.ast_indexer = ast_indexer

    def rescan(self) -> dict[str, Any]:
        """Perform a complete rescan and return status statistics."""
        logger.info("Triggering full documentation and code re-indexing...")

        # Snapshot counts before
        doc_sections_before = len(self.doc_indexer.sections)
        ast_symbols_before = len(self.ast_indexer._cache)

        # Reload
        self.who_catalog._load_catalog()
        doc_sections_after = self.doc_indexer.reindex()
        ast_symbols_after = self.ast_indexer.reindex()

        summary = {
            "who_families_loaded": len(self.who_catalog._families),
            "doc_sections": {
                "before": doc_sections_before,
                "after": doc_sections_after,
                "delta": doc_sections_after - doc_sections_before,
            },
            "ast_symbols": {
                "before": ast_symbols_before,
                "after": ast_symbols_after,
                "delta": ast_symbols_after - ast_symbols_before,
            },
            "status": "success",
        }
        logger.info("Rescan completed successfully: %s", summary)
        return summary
