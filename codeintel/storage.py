from __future__ import annotations

import datetime as dt
import hashlib
from collections import deque
from pathlib import Path
from typing import Any

from neural_memory.core.neuron import Neuron, NeuronType
from neural_memory.core.synapse import SynapseType, Synapse
from neural_memory.unified_config import get_shared_storage

from codeintel.parser import Edge, Symbol


class CodeIntelStorage:
    def __init__(self, storage=None):
        self.storage = storage

    async def _ensure_storage(self) -> None:
        if self.storage is None:
            self.storage = await get_shared_storage()

    async def create_generation(self, project_path: str) -> str:
        await self._ensure_storage()
        normalized_path = self._normalize_project_path(project_path)
        generation_id = hashlib.sha256(
            f"{normalized_path}:{dt.datetime.now(dt.UTC).isoformat()}".encode("utf-8")
        ).hexdigest()[:16]
        neuron = Neuron.create(
            type=NeuronType.CONCEPT,
            content=f"codeintel_generation:{generation_id}:{normalized_path}",
            metadata={
                "tags": ["codeintel_generation"],
                "generation_id": generation_id,
                "project_path": normalized_path,
                "status": "building",
                "created_at": dt.datetime.now(dt.UTC).isoformat(),
                "symbol_count": 0,
                "edge_count": 0,
                "skipped_files": 0,
            },
            neuron_id=f"codeintel-generation:{generation_id}",
        )
        await self.storage.add_neuron(neuron)
        return generation_id

    async def store_symbol(self, symbol: Symbol, generation_id: str, project_path: str) -> str:
        await self._ensure_storage()
        normalized_path = self._normalize_project_path(project_path)
        neuron_id = self._symbol_neuron_id(symbol.symbol_id, generation_id)
        neuron = Neuron.create(
            type=NeuronType.ENTITY,
            content=f"{symbol.kind}: {symbol.qualified_name} in {symbol.file}:{symbol.line}",
            metadata={
                "tags": ["codeintel", symbol.kind, symbol.language],
                "symbol_id": symbol.symbol_id,
                "project_path": normalized_path,
                "generation_id": generation_id,
                "file": symbol.file,
                "line": symbol.line,
                "kind": symbol.kind,
                "language": symbol.language,
                "name": symbol.name,
                "qualified_name": symbol.qualified_name,
                "signature": symbol.signature,
            },
            neuron_id=neuron_id,
        )
        try:
            return await self.storage.add_neuron(neuron)
        except ValueError:
            existing = await self.storage.get_neuron(neuron_id)
            if existing is not None:
                await self.storage.update_neuron(neuron)
                return existing.id
            raise

    async def store_edge(self, edge: Edge, generation_id: str, project_path: str) -> str:
        await self._ensure_storage()
        normalized_path = self._normalize_project_path(project_path)
        source_id = self._symbol_neuron_id(edge.source_sid, generation_id)
        target_id = self._symbol_neuron_id(edge.target_sid, generation_id)
        synapse_id = hashlib.sha256(
            f"{generation_id}:{edge.source_sid}:{edge.type}:{edge.target_sid}".encode("utf-8")
        ).hexdigest()
        synapse = Synapse.create(
            source_id=source_id,
            target_id=target_id,
            type=SynapseType.RELATED_TO,
            weight=1.0,
            metadata={
                "tags": ["codeintel"],
                "edge_type": edge.type,
                "project_path": normalized_path,
                "generation_id": generation_id,
                "source_symbol_id": edge.source_sid,
                "target_symbol_id": edge.target_sid,
                "line": edge.line,
            },
            synapse_id=synapse_id,
        )
        try:
            return await self.storage.add_synapse(synapse)
        except ValueError:
            return synapse_id

    async def store_file_symbols(
        self,
        symbols: list[Symbol],
        generation_id: str,
        project_path: str,
    ) -> int:
        await self._ensure_storage()
        created_ids: list[str] = []
        try:
            for symbol in symbols:
                neuron_id = self._symbol_neuron_id(symbol.symbol_id, generation_id)
                existing = await self.storage.get_neuron(neuron_id)
                await self.store_symbol(symbol, generation_id, project_path)
                if existing is None:
                    created_ids.append(neuron_id)
            return len(symbols)
        except Exception:
            for neuron_id in reversed(created_ids):
                await self.storage.delete_neuron(neuron_id)
            raise

    async def store_edges_batch(
        self,
        edges: list[Edge],
        generation_id: str,
        project_path: str,
    ) -> int:
        await self._ensure_storage()
        stored = 0
        for edge in edges:
            source_id = self._symbol_neuron_id(edge.source_sid, generation_id)
            target_id = self._symbol_neuron_id(edge.target_sid, generation_id)
            if await self.storage.get_neuron(source_id) is None:
                continue
            if await self.storage.get_neuron(target_id) is None:
                continue
            await self.store_edge(edge, generation_id, project_path)
            stored += 1
        return stored

    async def activate_generation(
        self,
        generation_id: str,
        project_path: str,
        *,
        symbol_count: int | None = None,
        edge_count: int | None = None,
        skipped_files: int | None = None,
    ) -> None:
        await self._ensure_storage()
        normalized_path = self._normalize_project_path(project_path)
        actual_symbols, actual_edges = await self._count_generation_contents(
            generation_id,
            normalized_path,
        )
        if symbol_count is not None and actual_symbols != symbol_count:
            raise ValueError(
                f"Generation {generation_id} symbol count mismatch: {actual_symbols} != {symbol_count}"
            )
        if edge_count is not None and actual_edges != edge_count:
            raise ValueError(
                f"Generation {generation_id} edge count mismatch: {actual_edges} != {edge_count}"
            )
        for generation in await self._generation_neurons(normalized_path):
            if generation.metadata.get("generation_id") == generation_id:
                metadata: dict[str, Any] = {
                    "status": "active",
                    "symbol_count": actual_symbols,
                    "edge_count": actual_edges,
                }
                if skipped_files is not None:
                    metadata["skipped_files"] = skipped_files
                await self.storage.update_neuron(generation.with_metadata(**metadata))
            elif generation.metadata.get("status") == "active":
                await self.storage.update_neuron(generation.with_metadata(status="gc"))

    async def fail_generation(self, generation_id: str, project_path: str, error: str) -> None:
        await self._ensure_storage()
        normalized_path = self._normalize_project_path(project_path)
        for generation in await self._generation_neurons(normalized_path):
            if generation.metadata.get("generation_id") == generation_id:
                await self.storage.update_neuron(
                    generation.with_metadata(status="failed", error=error)
                )
                return

    async def clear_index(self, project_path: str) -> dict[str, int]:
        await self._ensure_storage()
        normalized_path = self._normalize_project_path(project_path)
        deleted = 0
        for neuron in await self.storage.find_neurons(limit=10000):
            tags = neuron.metadata.get("tags", [])
            if neuron.metadata.get("project_path") != normalized_path:
                continue
            if "codeintel" not in tags and "codeintel_generation" not in tags:
                continue
            deleted += int(await self.storage.delete_neuron(neuron.id))
        return {"deleted_neurons": deleted}

    async def find_symbol(
        self,
        query: str,
        project_path: str | None = None,
        kind: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        await self._ensure_storage()
        normalized_path = self._normalize_project_path(project_path) if project_path else None
        generation_neurons = await self._generation_neurons(normalized_path)
        active_generation_ids = await self._active_generation_ids(normalized_path)
        if generation_neurons and not active_generation_ids:
            return []
        neurons = await self.storage.find_neurons(content_contains=query, limit=1000)
        lowered_query = query.lower()
        results = []
        for neuron in neurons:
            if not self._is_active_symbol(
                neuron,
                normalized_path,
                active_generation_ids,
                kind=kind,
            ):
                continue
            if not self._matches_query(neuron, lowered_query):
                continue
            results.append(self._format_symbol(neuron))
        results.sort(key=lambda item: (item["qualified_name"], item["file"], item["line"]))
        return results[:limit]

    async def find_callers(
        self,
        symbol_id: str,
        project_path: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        return await self._linked_symbols(
            symbol_id,
            project_path=project_path,
            direction="in",
            limit=limit,
        )

    async def find_callees(
        self,
        symbol_id: str,
        project_path: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        return await self._linked_symbols(
            symbol_id,
            project_path=project_path,
            direction="out",
            limit=limit,
        )

    async def find_impact(
        self,
        symbol_id: str,
        project_path: str | None = None,
        max_depth: int = 3,
        max_results: int = 100,
    ) -> dict[str, Any]:
        await self._ensure_storage()
        normalized_path = self._normalize_project_path(project_path) if project_path else None
        start_neurons = await self._active_neurons_for_symbol(symbol_id, normalized_path)
        queue = deque((neuron, 0) for neuron in start_neurons)
        visited_neuron_ids = {neuron.id for neuron in start_neurons}
        collected: dict[str, dict[str, Any]] = {}
        truncated = False

        while queue:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for neighbor, synapse in await self.storage.get_neighbors(current.id, direction="in"):
                if not self._is_codeintel_call_edge(synapse):
                    continue
                if normalized_path and neighbor.metadata.get("project_path") != normalized_path:
                    continue
                if neighbor.id in visited_neuron_ids:
                    continue
                visited_neuron_ids.add(neighbor.id)
                if len(collected) >= max_results:
                    truncated = True
                    continue
                collected[neighbor.metadata["symbol_id"]] = self._format_symbol(neighbor)
                queue.append((neighbor, depth + 1))

        affected_symbols = list(collected.values())
        affected_symbols.sort(key=lambda item: (item["qualified_name"], item["file"], item["line"]))
        affected_files = sorted({symbol["file"] for symbol in affected_symbols})
        risk = "low"
        if len(affected_symbols) >= 20:
            risk = "high"
        elif len(affected_symbols) >= 5:
            risk = "medium"

        return {
            "affected_files": affected_files,
            "affected_symbols": affected_symbols,
            "truncated": truncated,
            "total_visited": len(visited_neuron_ids),
            "risk": risk,
        }

    async def _linked_symbols(
        self,
        symbol_id: str,
        *,
        project_path: str | None,
        direction: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        await self._ensure_storage()
        normalized_path = self._normalize_project_path(project_path) if project_path else None
        active_neurons = await self._active_neurons_for_symbol(symbol_id, normalized_path)
        results: dict[str, dict[str, Any]] = {}

        for neuron in active_neurons:
            neighbors = await self.storage.get_neighbors(neuron.id, direction=direction)
            for neighbor, synapse in neighbors:
                if not self._is_codeintel_call_edge(synapse):
                    continue
                if normalized_path and neighbor.metadata.get("project_path") != normalized_path:
                    continue
                results[neighbor.metadata["symbol_id"]] = self._format_symbol(neighbor)

        ordered = list(results.values())
        ordered.sort(key=lambda item: (item["qualified_name"], item["file"], item["line"]))
        return ordered[:limit]

    async def _active_neurons_for_symbol(
        self,
        symbol_id: str,
        project_path: str | None,
    ) -> list[Neuron]:
        generation_neurons = await self._generation_neurons(project_path)
        active_generation_ids = await self._active_generation_ids(project_path)
        if generation_neurons and not active_generation_ids:
            return []
        matches: list[Neuron] = []
        for neuron in await self.storage.find_neurons(limit=10000):
            if not self._is_active_symbol(neuron, project_path, active_generation_ids):
                continue
            if neuron.metadata.get("symbol_id") == symbol_id:
                matches.append(neuron)
        return matches

    async def _generation_neurons(self, project_path: str | None = None) -> list[Neuron]:
        neurons = await self.storage.find_neurons(content_contains="codeintel_generation:", limit=10000)
        results: list[Neuron] = []
        for neuron in neurons:
            tags = neuron.metadata.get("tags", [])
            if "codeintel_generation" not in tags:
                continue
            if project_path and neuron.metadata.get("project_path") != project_path:
                continue
            results.append(neuron)
        return results

    async def _active_generation_ids(self, project_path: str | None) -> set[str]:
        return {
            neuron.metadata["generation_id"]
            for neuron in await self._generation_neurons(project_path)
            if neuron.metadata.get("status") == "active"
        }

    def _is_active_symbol(
        self,
        neuron: Neuron,
        project_path: str | None,
        active_generation_ids: set[str],
        *,
        kind: str | None = None,
    ) -> bool:
        tags = neuron.metadata.get("tags", [])
        if "codeintel" not in tags:
            return False
        if project_path and neuron.metadata.get("project_path") != project_path:
            return False
        if active_generation_ids and neuron.metadata.get("generation_id") not in active_generation_ids:
            return False
        if kind and neuron.metadata.get("kind") != kind:
            return False
        return True

    @staticmethod
    def _is_codeintel_edge(synapse: Synapse, edge_type: str | None = None) -> bool:
        if synapse.type != SynapseType.RELATED_TO:
            return False
        if "codeintel" not in synapse.metadata.get("tags", []):
            return False
        if edge_type is None:
            return True
        return synapse.metadata.get("edge_type") == edge_type

    @classmethod
    def _is_codeintel_call_edge(cls, synapse: Synapse) -> bool:
        return cls._is_codeintel_edge(synapse, "CALLS")

    @staticmethod
    def _matches_query(neuron: Neuron, lowered_query: str) -> bool:
        haystacks = [
            str(neuron.metadata.get("name", "")).lower(),
            str(neuron.metadata.get("qualified_name", "")).lower(),
            str(neuron.metadata.get("kind", "")).lower(),
            str(neuron.metadata.get("language", "")).lower(),
        ]
        return any(lowered_query in haystack for haystack in haystacks)

    @staticmethod
    def _format_symbol(neuron: Neuron) -> dict[str, Any]:
        return {
            "id": neuron.id,
            "symbol_id": neuron.metadata.get("symbol_id"),
            "name": neuron.metadata.get("name"),
            "qualified_name": neuron.metadata.get("qualified_name"),
            "kind": neuron.metadata.get("kind"),
            "language": neuron.metadata.get("language"),
            "file": neuron.metadata.get("file"),
            "line": neuron.metadata.get("line"),
        }

    @staticmethod
    def _normalize_project_path(project_path: str | None) -> str | None:
        if project_path is None:
            return None
        return str(Path(project_path).resolve())

    @staticmethod
    def _symbol_neuron_id(symbol_id: str, generation_id: str) -> str:
        return f"{generation_id}:{symbol_id}"

    async def _count_generation_contents(
        self,
        generation_id: str,
        project_path: str,
    ) -> tuple[int, int]:
        symbols = 0
        for neuron in await self.storage.find_neurons(limit=10000):
            if "codeintel" not in neuron.metadata.get("tags", []):
                continue
            if neuron.metadata.get("generation_id") != generation_id:
                continue
            if neuron.metadata.get("project_path") != project_path:
                continue
            symbols += 1

        edges = 0
        for synapse in await self.storage.get_synapses(type=SynapseType.RELATED_TO):
            if not self._is_codeintel_edge(synapse):
                continue
            if synapse.metadata.get("generation_id") != generation_id:
                continue
            if synapse.metadata.get("project_path") != project_path:
                continue
            edges += 1
        return symbols, edges
