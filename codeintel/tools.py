from __future__ import annotations

import os
import time
from typing import Any

from neural_memory.plugins import register
from neural_memory.plugins.base import ProPlugin

from codeintel.parser import CodeIntelParser
from codeintel.storage import CodeIntelStorage


class CodeIntelPlugin(ProPlugin):
    @property
    def name(self) -> str:
        return "codeintel"

    @property
    def version(self) -> str:
        return "0.1.0"

    def get_retrieval_strategies(self):
        return {}

    def get_compression_fn(self):
        return None

    def get_consolidation_strategies(self):
        return {}

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "nmem_codeintel_index",
                "description": "Index a codebase for intelligence queries (JS/TS/Python).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Absolute path to codebase"},
                        "extensions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional extension allow-list",
                        },
                        "max_files": {"type": "integer", "default": 5000},
                        "force": {"type": "boolean", "default": False},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "nmem_codeintel_search",
                "description": "Search active code symbols across indexed projects.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "kind": {"type": "string"},
                        "project_path": {"type": "string"},
                        "limit": {"type": "integer", "default": 20},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "nmem_codeintel_callers",
                "description": "Find active callers for a symbol.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "symbol_id": {"type": "string"},
                        "project_path": {"type": "string"},
                        "limit": {"type": "integer", "default": 20},
                    },
                    "required": ["symbol_id"],
                },
            },
            {
                "name": "nmem_codeintel_callees",
                "description": "Find active callees for a symbol.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "symbol_id": {"type": "string"},
                        "project_path": {"type": "string"},
                        "limit": {"type": "integer", "default": 20},
                    },
                    "required": ["symbol_id"],
                },
            },
            {
                "name": "nmem_codeintel_impact",
                "description": "Compute reverse-call impact for an active symbol.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "symbol_id": {"type": "string"},
                        "project_path": {"type": "string"},
                        "max_depth": {"type": "integer", "default": 3},
                        "max_results": {"type": "integer", "default": 100},
                    },
                    "required": ["symbol_id"],
                },
            },
        ]

    def get_tool_handler(self, tool_name: str):
        return {
            "nmem_codeintel_index": self._handle_index,
            "nmem_codeintel_search": self._handle_search,
            "nmem_codeintel_callers": self._handle_callers,
            "nmem_codeintel_callees": self._handle_callees,
            "nmem_codeintel_impact": self._handle_impact,
        }.get(tool_name)

    async def _handle_index(self, server, arguments):
        path = arguments.get("path")
        if not path:
            return {"error": "Path required"}

        project_path = os.path.abspath(path)
        max_files = int(arguments.get("max_files", 5000))
        extensions = arguments.get("extensions")
        force = bool(arguments.get("force", False))

        storage = CodeIntelStorage(await server.get_storage())
        parser = CodeIntelParser()

        if force:
            await storage.clear_index(project_path)

        scan_report = parser.scan_project_report(
            project_path,
            max_files=max_files,
            extensions=extensions,
        )
        files = scan_report.supported_files
        if not files:
            if scan_report.planned_files:
                return {
                    "status": "unsupported",
                    "files_scanned": 0,
                    "planned_files": scan_report.planned_files,
                    "planned_languages": scan_report.planned_languages,
                    "message": "Only planned-v2 languages were found for this path",
                }
            return {"error": f"No supported files found in {project_path}"}

        started_at = time.perf_counter()
        generation_id = await storage.create_generation(project_path)
        symbols_found = 0
        edges_found = 0
        skipped_files = 0
        parsed_files: list[tuple[list, list]] = []

        try:
            for filepath in files:
                try:
                    symbols = parser.parse_file(filepath, project_path)
                    edges = parser.extract_edges(filepath, project_path, symbols)
                    stored_symbols = await storage.store_file_symbols(
                        symbols,
                        generation_id,
                        project_path,
                    )
                    symbols_found += stored_symbols
                    parsed_files.append((symbols, edges))
                except Exception:
                    skipped_files += 1
            for _, edges in parsed_files:
                edges_found += await storage.store_edges_batch(
                    edges,
                    generation_id,
                    project_path,
                )
            if not parsed_files:
                error = f"No files indexed successfully in {project_path}"
                await storage.fail_generation(generation_id, project_path, error)
                return {
                    "error": error,
                    "generation_id": generation_id,
                    "files_scanned": len(files),
                    "skipped": skipped_files,
                }
            await storage.activate_generation(
                generation_id,
                project_path,
                symbol_count=symbols_found,
                edge_count=edges_found,
                skipped_files=skipped_files,
            )
        except Exception as exc:
            await storage.fail_generation(generation_id, project_path, str(exc))
            raise

        result = {
            "status": "success",
            "generation_id": generation_id,
            "files_scanned": len(files),
            "symbols": symbols_found,
            "edges": edges_found,
            "skipped": skipped_files,
            "time": round(time.perf_counter() - started_at, 3),
        }
        if scan_report.planned_files:
            result["planned_files"] = scan_report.planned_files
            result["planned_languages"] = scan_report.planned_languages
        return result

    async def _handle_search(self, server, arguments):
        storage = CodeIntelStorage(await server.get_storage())
        return {
            "symbols": await storage.find_symbol(
                arguments["query"],
                project_path=arguments.get("project_path"),
                kind=arguments.get("kind"),
                limit=int(arguments.get("limit", 20)),
            )
        }

    async def _handle_callers(self, server, arguments):
        storage = CodeIntelStorage(await server.get_storage())
        return {
            "symbols": await storage.find_callers(
                arguments["symbol_id"],
                project_path=arguments.get("project_path"),
                limit=int(arguments.get("limit", 20)),
            )
        }

    async def _handle_callees(self, server, arguments):
        storage = CodeIntelStorage(await server.get_storage())
        return {
            "symbols": await storage.find_callees(
                arguments["symbol_id"],
                project_path=arguments.get("project_path"),
                limit=int(arguments.get("limit", 20)),
            )
        }

    async def _handle_impact(self, server, arguments):
        storage = CodeIntelStorage(await server.get_storage())
        return await storage.find_impact(
            arguments["symbol_id"],
            project_path=arguments.get("project_path"),
            max_depth=int(arguments.get("max_depth", 3)),
            max_results=int(arguments.get("max_results", 100)),
        )


def register_plugin() -> None:
    register(CodeIntelPlugin())
