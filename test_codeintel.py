from __future__ import annotations

from pathlib import Path

import pytest

from codeintel.parser import CodeIntelParser, Edge, Symbol
from codeintel.storage import CodeIntelStorage
from codeintel.tools import CodeIntelPlugin
from neural_memory.core.neuron import Neuron
from neural_memory.core.synapse import Synapse, SynapseType


class FakeStorage:
    def __init__(self) -> None:
        self.neurons: dict[str, Neuron] = {}
        self.synapses: dict[str, Synapse] = {}

    async def add_neuron(self, neuron: Neuron) -> str:
        if neuron.id in self.neurons:
            raise ValueError(f"Neuron {neuron.id} already exists")
        self.neurons[neuron.id] = neuron
        return neuron.id

    async def get_neuron(self, neuron_id: str) -> Neuron | None:
        return self.neurons.get(neuron_id)

    async def find_neurons(
        self,
        type=None,
        content_contains=None,
        content_exact=None,
        time_range=None,
        limit: int = 100,
        offset: int = 0,
        ephemeral=None,
    ) -> list[Neuron]:
        results = list(self.neurons.values())
        if type is not None:
            results = [neuron for neuron in results if neuron.type == type]
        if content_exact is not None:
            results = [neuron for neuron in results if neuron.content == content_exact]
        if content_contains is not None:
            needle = content_contains.lower()
            results = [neuron for neuron in results if needle in neuron.content.lower()]
        return results[offset : offset + limit]

    async def update_neuron(self, neuron: Neuron) -> None:
        if neuron.id not in self.neurons:
            raise ValueError(f"Neuron {neuron.id} does not exist")
        self.neurons[neuron.id] = neuron

    async def delete_neuron(self, neuron_id: str) -> bool:
        if neuron_id not in self.neurons:
            return False
        del self.neurons[neuron_id]
        stale_synapses = [
            synapse_id
            for synapse_id, synapse in self.synapses.items()
            if synapse.source_id == neuron_id or synapse.target_id == neuron_id
        ]
        for synapse_id in stale_synapses:
            del self.synapses[synapse_id]
        return True

    async def add_synapse(self, synapse: Synapse) -> str:
        if synapse.id in self.synapses:
            raise ValueError(f"Synapse {synapse.id} already exists")
        if synapse.source_id not in self.neurons or synapse.target_id not in self.neurons:
            raise ValueError("Source/target neuron missing")
        self.synapses[synapse.id] = synapse
        return synapse.id

    async def get_synapses(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        type: SynapseType | None = None,
        min_weight: float | None = None,
    ) -> list[Synapse]:
        results = list(self.synapses.values())
        if source_id is not None:
            results = [synapse for synapse in results if synapse.source_id == source_id]
        if target_id is not None:
            results = [synapse for synapse in results if synapse.target_id == target_id]
        if type is not None:
            results = [synapse for synapse in results if synapse.type == type]
        if min_weight is not None:
            results = [synapse for synapse in results if synapse.weight >= min_weight]
        return results

    async def update_synapse(self, synapse: Synapse) -> None:
        if synapse.id not in self.synapses:
            raise ValueError(f"Synapse {synapse.id} does not exist")
        self.synapses[synapse.id] = synapse

    async def delete_synapse(self, synapse_id: str) -> bool:
        if synapse_id not in self.synapses:
            return False
        del self.synapses[synapse_id]
        return True

    async def get_neighbors(
        self,
        neuron_id: str,
        direction: str = "both",
        synapse_types: list[SynapseType] | None = None,
        min_weight: float | None = None,
    ) -> list[tuple[Neuron, Synapse]]:
        results: list[tuple[Neuron, Synapse]] = []
        for synapse in self.synapses.values():
            if synapse_types and synapse.type not in synapse_types:
                continue
            if min_weight is not None and synapse.weight < min_weight:
                continue
            if direction in ("out", "both") and synapse.source_id == neuron_id:
                results.append((self.neurons[synapse.target_id], synapse))
            if direction in ("in", "both") and synapse.target_id == neuron_id:
                results.append((self.neurons[synapse.source_id], synapse))
        return results


class FakeServer:
    def __init__(self, storage: FakeStorage) -> None:
        self._storage = storage

    async def get_storage(self) -> FakeStorage:
        return self._storage


class FailingStorage(FakeStorage):
    def __init__(self, fail_qualified_name: str) -> None:
        super().__init__()
        self.fail_qualified_name = fail_qualified_name

    async def add_neuron(self, neuron: Neuron) -> str:
        if neuron.metadata.get("qualified_name") == self.fail_qualified_name:
            raise RuntimeError("synthetic failure")
        return await super().add_neuron(neuron)


@pytest.fixture
def parser() -> CodeIntelParser:
    return CodeIntelParser()


def test_parse_python_symbols_and_edges(tmp_path: Path, parser: CodeIntelParser) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    (project / "util.py").write_text(
        "\n".join(
            [
                "def helper():",
                "    return 'ok'",
            ]
        ),
        encoding="utf-8",
    )
    source = project / "sample.py"
    source.write_text(
        "\n".join(
            [
                "from util import helper",
                "",
                "class Base:",
                "    pass",
                "",
                "class Greeter(Base):",
                "    def greet(self):",
                "        helper()",
            ]
        ),
        encoding="utf-8",
    )

    symbols = parser.parse_file(str(source), str(project))
    edges = parser.extract_edges(str(source), str(project), symbols)

    assert {(symbol.qualified_name, symbol.kind) for symbol in symbols} == {
        ("sample.py", "module"),
        ("Base", "class"),
        ("Greeter", "class"),
        ("Greeter.greet", "method"),
    }

    module_sid = next(symbol.symbol_id for symbol in symbols if symbol.qualified_name == "sample.py")
    base_sid = next(symbol.symbol_id for symbol in symbols if symbol.qualified_name == "Base")
    greeter_sid = next(symbol.symbol_id for symbol in symbols if symbol.qualified_name == "Greeter")
    greet_sid = next(symbol.symbol_id for symbol in symbols if symbol.qualified_name == "Greeter.greet")
    util_module_sid = parser_symbol("util.py", "module", "util.py", 1, "python", str(project)).symbol_id
    helper_sid = parser_symbol(
        "helper",
        "function",
        "util.py",
        1,
        "python",
        str(project),
        signature="()",
    ).symbol_id

    assert {(edge.source_sid, edge.target_sid, edge.type) for edge in edges} == {
        (module_sid, util_module_sid, "IMPORTS"),
        (module_sid, base_sid, "CONTAINS"),
        (module_sid, greeter_sid, "CONTAINS"),
        (greeter_sid, greet_sid, "CONTAINS"),
        (greeter_sid, base_sid, "EXTENDS"),
        (greet_sid, helper_sid, "CALLS"),
    }


def test_parse_typescript_symbols_and_edges(tmp_path: Path, parser: CodeIntelParser) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    (project / "mod.ts").write_text(
        "\n".join(
            [
                "export interface Runner {}",
                "export class Base {}",
                "export function helper() {}",
            ]
        ),
        encoding="utf-8",
    )
    source = project / "sample.ts"
    source.write_text(
        "\n".join(
            [
                "import { Runner, Base, helper } from './mod';",
                "class Greeter extends Base implements Runner {",
                "  run() { return helper(); }",
                "}",
            ]
        ),
        encoding="utf-8",
    )

    symbols = parser.parse_file(str(source), str(project))
    edges = parser.extract_edges(str(source), str(project), symbols)

    assert {(symbol.qualified_name, symbol.kind) for symbol in symbols} == {
        ("sample.ts", "module"),
        ("Greeter", "class"),
        ("Greeter.run", "method"),
    }

    module_sid = next(symbol.symbol_id for symbol in symbols if symbol.qualified_name == "sample.ts")
    greeter_sid = next(symbol.symbol_id for symbol in symbols if symbol.qualified_name == "Greeter")
    run_sid = next(symbol.symbol_id for symbol in symbols if symbol.qualified_name == "Greeter.run")
    mod_module_sid = parser_symbol("mod.ts", "module", "mod.ts", 1, "typescript", str(project)).symbol_id
    base_sid = parser_symbol("Base", "class", "mod.ts", 2, "typescript", str(project)).symbol_id
    runner_sid = parser_symbol("Runner", "interface", "mod.ts", 1, "typescript", str(project)).symbol_id
    helper_sid = parser_symbol(
        "helper",
        "function",
        "mod.ts",
        3,
        "typescript",
        str(project),
        signature="()",
    ).symbol_id

    assert {(edge.source_sid, edge.target_sid, edge.type) for edge in edges} == {
        (module_sid, mod_module_sid, "IMPORTS"),
        (module_sid, greeter_sid, "CONTAINS"),
        (greeter_sid, run_sid, "CONTAINS"),
        (greeter_sid, base_sid, "EXTENDS"),
        (greeter_sid, runner_sid, "IMPLEMENTS"),
        (run_sid, helper_sid, "CALLS"),
    }


@pytest.mark.asyncio
async def test_plugin_reports_unsupported_languages(tmp_path: Path) -> None:
    project = tmp_path / "unsupported_proj"
    project.mkdir()
    (project / "main.go").write_text("package main\nfunc main() {}\n", encoding="utf-8")

    plugin = CodeIntelPlugin()
    server = FakeServer(FakeStorage())

    result = await plugin._handle_index(server, {"path": str(project)})

    assert result["status"] == "unsupported"
    assert result["files_scanned"] == 0
    assert result["planned_languages"] == ["go"]
    assert result["planned_files"] == ["main.go"]


@pytest.mark.asyncio
async def test_storage_generation_and_queries(tmp_path: Path) -> None:
    project_path = str(tmp_path / "proj")
    backend = FakeStorage()
    storage = CodeIntelStorage(backend)

    generation_one = await storage.create_generation(project_path)
    module_symbol = parser_symbol("alpha.py", "module", "alpha.py", 1, "python", project_path)
    alpha_symbol = parser_symbol("alpha", "function", "alpha.py", 1, "python", project_path)
    beta_symbol = parser_symbol("beta", "function", "alpha.py", 4, "python", project_path)

    await storage.store_symbol(module_symbol, generation_one, project_path)
    alpha_id = await storage.store_symbol(alpha_symbol, generation_one, project_path)
    await storage.store_symbol(beta_symbol, generation_one, project_path)
    await storage.store_edge(
        parser_edge(module_symbol.symbol_id, alpha_symbol.symbol_id, "CONTAINS", 1),
        generation_one,
        project_path,
    )
    await storage.store_edge(
        parser_edge(module_symbol.symbol_id, beta_symbol.symbol_id, "CONTAINS", 4),
        generation_one,
        project_path,
    )
    await storage.store_edge(
        parser_edge(alpha_symbol.symbol_id, beta_symbol.symbol_id, "CALLS", 2),
        generation_one,
        project_path,
    )
    await storage.activate_generation(
        generation_one,
        project_path,
        symbol_count=3,
        edge_count=3,
    )

    matches = await storage.find_symbol("alpha", project_path=project_path)
    assert [match["qualified_name"] for match in matches] == ["alpha", "alpha.py"]

    callees = await storage.find_callees(alpha_symbol.symbol_id, project_path=project_path)
    assert [callee["qualified_name"] for callee in callees] == ["beta"]

    callers = await storage.find_callers(beta_symbol.symbol_id, project_path=project_path)
    assert [caller["qualified_name"] for caller in callers] == ["alpha"]

    impact = await storage.find_impact(beta_symbol.symbol_id, project_path=project_path)
    assert impact["affected_files"] == ["alpha.py"]
    assert [symbol["qualified_name"] for symbol in impact["affected_symbols"]] == ["alpha"]

    generation_one_neuron = generation_neuron(backend, generation_one)
    assert generation_one_neuron.metadata["status"] == "active"
    assert generation_one_neuron.metadata["symbol_count"] == 3
    assert generation_one_neuron.metadata["edge_count"] == 3

    generation_two = await storage.create_generation(project_path)
    beta_v2 = parser_symbol("beta_v2", "function", "alpha.py", 4, "python", project_path)
    await storage.store_symbol(module_symbol, generation_two, project_path)
    await storage.store_symbol(beta_v2, generation_two, project_path)
    await storage.activate_generation(
        generation_two,
        project_path,
        symbol_count=2,
        edge_count=0,
    )

    generation_two_neuron = generation_neuron(backend, generation_two)
    assert generation_two_neuron.metadata["status"] == "active"
    assert generation_neuron(backend, generation_one).metadata["status"] == "gc"

    post_swap = await storage.find_symbol("beta", project_path=project_path)
    assert [match["qualified_name"] for match in post_swap] == ["beta_v2"]

    generation_three = await storage.create_generation(project_path)
    gamma = parser_symbol("gamma", "function", "gamma.py", 1, "python", project_path)
    await storage.store_symbol(gamma, generation_three, project_path)
    await storage.fail_generation(generation_three, project_path, "boom")

    failed_generation = generation_neuron(backend, generation_three)
    assert failed_generation.metadata["status"] == "failed"
    assert failed_generation.metadata["error"] == "boom"
    assert await storage.find_symbol("gamma", project_path=project_path) == []
    assert alpha_id.startswith(f"{generation_one}:")


@pytest.mark.asyncio
async def test_plugin_rolls_back_failed_file_and_indexes_remaining_files(tmp_path: Path) -> None:
    project = tmp_path / "rollback_proj"
    project.mkdir()
    (project / "good.py").write_text(
        "\n".join(
            [
                "def helper():",
                "    return 'ok'",
                "",
                "def run():",
                "    return helper()",
            ]
        ),
        encoding="utf-8",
    )
    (project / "broken.py").write_text(
        "\n".join(
            [
                "def stable():",
                "    return 1",
                "",
                "def explode():",
                "    return stable()",
            ]
        ),
        encoding="utf-8",
    )

    backend = FailingStorage("explode")
    plugin = CodeIntelPlugin()
    server = FakeServer(backend)

    result = await plugin._handle_index(server, {"path": str(project), "force": True})

    assert result["status"] == "success"
    assert result["files_scanned"] == 2
    assert result["skipped"] == 1

    broken_symbols = [
        neuron
        for neuron in backend.neurons.values()
        if neuron.metadata.get("file") == "broken.py"
        and "codeintel" in neuron.metadata.get("tags", [])
    ]
    assert broken_symbols == []

    search_result = await plugin._handle_search(
        server,
        {"query": "run", "project_path": str(project)},
    )
    assert [symbol["qualified_name"] for symbol in search_result["symbols"]] == ["run"]


@pytest.mark.asyncio
async def test_plugin_index_and_graph_tools(tmp_path: Path) -> None:
    project = tmp_path / "plugin_proj"
    project.mkdir()
    (project / "util.py").write_text(
        "\n".join(
            [
                "def helper():",
                "    return 'ok'",
            ]
        ),
        encoding="utf-8",
    )
    (project / "service.py").write_text(
        "\n".join(
            [
                "from util import helper",
                "",
                "def run():",
                "    return helper()",
            ]
        ),
        encoding="utf-8",
    )

    plugin = CodeIntelPlugin()
    server = FakeServer(FakeStorage())

    index_result = await plugin._handle_index(
        server,
        {"path": str(project), "force": True},
    )
    assert index_result["status"] == "success"
    assert index_result["symbols"] == 4
    assert index_result["edges"] == 4

    search_result = await plugin._handle_search(
        server,
        {"query": "run", "project_path": str(project)},
    )
    run_symbol = next(
        symbol for symbol in search_result["symbols"] if symbol["qualified_name"] == "run"
    )

    callees_result = await plugin._handle_callees(
        server,
        {"symbol_id": run_symbol["symbol_id"], "project_path": str(project)},
    )
    assert [entry["qualified_name"] for entry in callees_result["symbols"]] == ["helper"]

    helper_symbol_id = callees_result["symbols"][0]["symbol_id"]
    impact_result = await plugin._handle_impact(
        server,
        {"symbol_id": helper_symbol_id, "project_path": str(project)},
    )
    assert [symbol["qualified_name"] for symbol in impact_result["affected_symbols"]] == ["run"]


def generation_neuron(storage: FakeStorage, generation_id: str) -> Neuron:
    return next(
        neuron
        for neuron in storage.neurons.values()
        if neuron.metadata.get("generation_id") == generation_id
        and "codeintel_generation" in neuron.metadata.get("tags", [])
    )


def parser_symbol(
    qualified_name: str,
    kind: str,
    file: str,
    line: int,
    language: str,
    project_path: str,
    *,
    signature: str = "",
) -> Symbol:
    return Symbol(
        name=qualified_name.split(".")[-1],
        qualified_name=qualified_name,
        kind=kind,
        file=file,
        line=line,
        language=language,
        project_path=str(Path(project_path).resolve()),
        signature=signature,
    )


def parser_edge(source_sid: str, target_sid: str, edge_type: str, line: int) -> Edge:
    return Edge(source_sid=source_sid, target_sid=target_sid, type=edge_type, line=line)
