from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from tree_sitter import Language, Node, Parser
import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_typescript


@dataclass
class Symbol:
    name: str
    qualified_name: str
    kind: str
    file: str
    line: int
    language: str
    project_path: str
    signature: str = ""
    symbol_id: str = ""

    def __post_init__(self) -> None:
        if not self.symbol_id:
            raw = (
                f"{self.project_path}:{self.language}:{self.file}:"
                f"{self.qualified_name}:{self.signature}"
            )
            self.symbol_id = hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class Edge:
    source_sid: str
    target_sid: str
    type: str
    line: int


@dataclass
class ScanReport:
    supported_files: list[str]
    planned_files: list[str]
    planned_languages: list[str]


class CodeIntelParser:
    """Parse JS/TS/Python sources and extract a compact code graph."""

    SUPPORTED_V1 = {
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".py": "python",
    }

    PLANNED_V2 = {
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".rb": "ruby",
        ".php": "php",
    }

    def __init__(self) -> None:
        self._parsers: dict[str, Parser] = {}
        self._symbol_cache: dict[str, list[Symbol]] = {}
        self._parsing_files: set[str] = set()

    def is_supported(self, ext: str) -> bool | str:
        lowered = ext.lower()
        if lowered in self.SUPPORTED_V1:
            return True
        if lowered in self.PLANNED_V2:
            return "planned_v2"
        return False

    def scan_project(
        self,
        project_path: str,
        max_files: int = 5000,
        extensions: Iterable[str] | None = None,
        max_file_size: int = 1_000_000,
    ) -> list[str]:
        return self.scan_project_report(
            project_path,
            max_files=max_files,
            extensions=extensions,
            max_file_size=max_file_size,
        ).supported_files

    def scan_project_report(
        self,
        project_path: str,
        max_files: int = 5000,
        extensions: Iterable[str] | None = None,
        max_file_size: int = 1_000_000,
    ) -> ScanReport:
        root = Path(project_path).resolve()
        allowed_exts = {ext.lower() for ext in extensions} if extensions else None
        ignored_dirs = {".git", "node_modules", "__pycache__", "vendor", ".tmp-nmem"}
        supported_files: list[str] = []
        planned_files: list[str] = []
        planned_languages: set[str] = set()

        for current_root, dirs, files in os.walk(root):
            dirs[:] = [dirname for dirname in dirs if dirname not in ignored_dirs]
            for filename in files:
                ext = Path(filename).suffix.lower()
                if allowed_exts is not None and ext not in allowed_exts:
                    continue
                filepath = Path(current_root) / filename
                if filepath.is_symlink():
                    continue
                try:
                    if filepath.stat().st_size > max_file_size:
                        continue
                except OSError:
                    continue

                support = self.is_supported(ext)
                if support is True:
                    supported_files.append(str(filepath))
                    if len(supported_files) >= max_files:
                        return ScanReport(
                            supported_files=supported_files,
                            planned_files=sorted(planned_files),
                            planned_languages=sorted(planned_languages),
                        )
                    continue
                if support == "planned_v2":
                    planned_files.append(filepath.resolve().relative_to(root).as_posix())
                    planned_languages.add(self.PLANNED_V2[ext])

        return ScanReport(
            supported_files=supported_files,
            planned_files=sorted(planned_files),
            planned_languages=sorted(planned_languages),
        )

    def parse_file(self, filepath: str, project_path: str) -> list[Symbol]:
        parsed = self._parse(filepath, project_path)
        if parsed is None:
            return []

        absolute_path, tree, source_bytes, language_name, rel_path, normalized_project = parsed
        if absolute_path in self._symbol_cache:
            return list(self._symbol_cache[absolute_path])
        if absolute_path in self._parsing_files:
            return [self._module_symbol(rel_path, normalized_project, language_name)]

        self._parsing_files.add(absolute_path)
        try:
            module_symbol = self._module_symbol(rel_path, normalized_project, language_name)
            if language_name == "python":
                members = self._extract_python_symbols(
                    tree.root_node,
                    source_bytes,
                    rel_path,
                    normalized_project,
                )
            else:
                members = self._extract_javascript_symbols(
                    tree.root_node,
                    source_bytes,
                    rel_path,
                    normalized_project,
                    language_name,
                )
            symbols = [module_symbol, *members]
            self._symbol_cache[absolute_path] = symbols
            return list(symbols)
        finally:
            self._parsing_files.discard(absolute_path)

    def extract_edges(self, filepath: str, project_path: str, symbols: list[Symbol]) -> list[Edge]:
        parsed = self._parse(filepath, project_path)
        if parsed is None or not symbols:
            return []

        absolute_path, tree, source_bytes, language_name, rel_path, normalized_project = parsed
        module_symbol = next((symbol for symbol in symbols if symbol.kind == "module"), None)
        if module_symbol is None:
            module_symbol = self._module_symbol(rel_path, normalized_project, language_name)

        import_edges, import_bindings = self._collect_imports(
            absolute_path,
            tree.root_node,
            source_bytes,
            language_name,
            project_path,
            module_symbol,
        )
        contains_edges = self._collect_contains_edges(symbols)
        if language_name == "python":
            relation_edges = self._extract_python_relation_edges(
                tree.root_node,
                source_bytes,
                symbols,
                import_bindings,
            )
            call_edges = self._extract_call_edges(
                tree.root_node,
                source_bytes,
                symbols,
                import_bindings,
                python=True,
            )
        else:
            relation_edges = self._extract_javascript_relation_edges(
                tree.root_node,
                source_bytes,
                symbols,
                import_bindings,
            )
            call_edges = self._extract_call_edges(
                tree.root_node,
                source_bytes,
                symbols,
                import_bindings,
                python=False,
            )
        return self._dedupe_edges([*import_edges, *contains_edges, *relation_edges, *call_edges])

    def _parse(
        self,
        filepath: str,
        project_path: str,
    ) -> tuple[str, object, bytes, str, str, str] | None:
        ext = Path(filepath).suffix.lower()
        language_name = self.SUPPORTED_V1.get(ext)
        if language_name is None:
            return None

        normalized_project = str(Path(project_path).resolve())
        absolute_path = str(Path(filepath).resolve())
        rel_path = Path(absolute_path).relative_to(Path(normalized_project)).as_posix()
        try:
            source_bytes = Path(absolute_path).read_bytes()
        except OSError:
            return None

        parser = self._get_parser(language_name)
        return (
            absolute_path,
            parser.parse(source_bytes),
            source_bytes,
            language_name,
            rel_path,
            normalized_project,
        )

    def _get_parser(self, language_name: str) -> Parser:
        if language_name not in self._parsers:
            parser = Parser()
            parser.language = self._get_language(language_name)
            self._parsers[language_name] = parser
        return self._parsers[language_name]

    @staticmethod
    def _get_language(language_name: str) -> Language:
        if language_name == "python":
            return Language(tree_sitter_python.language())
        if language_name == "javascript":
            return Language(tree_sitter_javascript.language())
        if language_name == "typescript":
            return Language(tree_sitter_typescript.language_typescript())
        if language_name == "tsx":
            return Language(tree_sitter_typescript.language_tsx())
        raise ValueError(f"Unsupported language: {language_name}")

    def _extract_python_symbols(
        self,
        root: Node,
        source_bytes: bytes,
        rel_path: str,
        project_path: str,
    ) -> list[Symbol]:
        symbols: list[Symbol] = []

        def visit(node: Node, containers: list[str]) -> None:
            if node.type == "class_definition":
                name = self._node_text(node.child_by_field_name("name"), source_bytes)
                if name:
                    symbols.append(
                        Symbol(
                            name=name,
                            qualified_name=".".join([*containers, name]) if containers else name,
                            kind="class",
                            file=rel_path,
                            line=node.start_point[0] + 1,
                            language="python",
                            project_path=project_path,
                        )
                    )
                next_containers = [*containers, name] if name else containers
                for child in node.children:
                    visit(child, next_containers)
                return

            if node.type == "function_definition":
                name = self._node_text(node.child_by_field_name("name"), source_bytes)
                if name:
                    parameters = node.child_by_field_name("parameters")
                    symbols.append(
                        Symbol(
                            name=name,
                            qualified_name=".".join([*containers, name]) if containers else name,
                            kind="method" if containers else "function",
                            file=rel_path,
                            line=node.start_point[0] + 1,
                            language="python",
                            project_path=project_path,
                            signature=self._node_text(parameters, source_bytes) if parameters else "",
                        )
                    )
                next_containers = [*containers, name] if name else containers
                for child in node.children:
                    visit(child, next_containers)
                return

            for child in node.children:
                visit(child, containers)

        visit(root, [])
        return symbols

    def _extract_javascript_symbols(
        self,
        root: Node,
        source_bytes: bytes,
        rel_path: str,
        project_path: str,
        language_name: str,
    ) -> list[Symbol]:
        symbols: list[Symbol] = []
        public_language = self._public_language(language_name)

        def visit(node: Node, containers: list[str]) -> None:
            if node.type == "interface_declaration":
                name = self._node_text(node.child_by_field_name("name"), source_bytes)
                if name:
                    symbols.append(
                        Symbol(
                            name=name,
                            qualified_name=".".join([*containers, name]) if containers else name,
                            kind="interface",
                            file=rel_path,
                            line=node.start_point[0] + 1,
                            language=public_language,
                            project_path=project_path,
                        )
                    )
                next_containers = [*containers, name] if name else containers
                for child in node.children:
                    visit(child, next_containers)
                return

            if node.type == "class_declaration":
                name = self._node_text(node.child_by_field_name("name"), source_bytes)
                if name:
                    symbols.append(
                        Symbol(
                            name=name,
                            qualified_name=".".join([*containers, name]) if containers else name,
                            kind="class",
                            file=rel_path,
                            line=node.start_point[0] + 1,
                            language=public_language,
                            project_path=project_path,
                        )
                    )
                next_containers = [*containers, name] if name else containers
                for child in node.children:
                    visit(child, next_containers)
                return

            if node.type == "function_declaration":
                name = self._node_text(node.child_by_field_name("name"), source_bytes)
                if name:
                    parameters = node.child_by_field_name("parameters")
                    symbols.append(
                        Symbol(
                            name=name,
                            qualified_name=".".join([*containers, name]) if containers else name,
                            kind="function",
                            file=rel_path,
                            line=node.start_point[0] + 1,
                            language=public_language,
                            project_path=project_path,
                            signature=self._node_text(parameters, source_bytes) if parameters else "",
                        )
                    )
                next_containers = [*containers, name] if name else containers
                for child in node.children:
                    visit(child, next_containers)
                return

            if node.type == "method_definition":
                name = self._node_text(node.child_by_field_name("name"), source_bytes)
                if name:
                    parameters = node.child_by_field_name("parameters")
                    symbols.append(
                        Symbol(
                            name=name,
                            qualified_name=".".join([*containers, name]) if containers else name,
                            kind="method",
                            file=rel_path,
                            line=node.start_point[0] + 1,
                            language=public_language,
                            project_path=project_path,
                            signature=self._node_text(parameters, source_bytes) if parameters else "",
                        )
                    )
                next_containers = [*containers, name] if name else containers
                for child in node.children:
                    visit(child, next_containers)
                return

            if node.type == "variable_declarator":
                name = self._node_text(node.child_by_field_name("name"), source_bytes)
                value_node = node.child_by_field_name("value")
                if name and value_node is not None and value_node.type in {
                    "arrow_function",
                    "function",
                    "function_expression",
                }:
                    parameters = value_node.child_by_field_name("parameters")
                    symbols.append(
                        Symbol(
                            name=name,
                            qualified_name=".".join([*containers, name]) if containers else name,
                            kind="function",
                            file=rel_path,
                            line=node.start_point[0] + 1,
                            language=public_language,
                            project_path=project_path,
                            signature=self._node_text(parameters, source_bytes) if parameters else "",
                        )
                    )
                next_containers = [*containers, name] if name else containers
                for child in node.children:
                    visit(child, next_containers)
                return

            for child in node.children:
                visit(child, containers)

        visit(root, [])
        return symbols

    def _collect_imports(
        self,
        absolute_path: str,
        root: Node,
        source_bytes: bytes,
        language_name: str,
        project_path: str,
        module_symbol: Symbol,
    ) -> tuple[list[Edge], dict[str, Symbol]]:
        if language_name == "python":
            return self._collect_python_imports(
                absolute_path,
                root,
                source_bytes,
                project_path,
                module_symbol,
            )
        return self._collect_javascript_imports(
            absolute_path,
            root,
            source_bytes,
            project_path,
            module_symbol,
        )

    def _collect_python_imports(
        self,
        absolute_path: str,
        root: Node,
        source_bytes: bytes,
        project_path: str,
        module_symbol: Symbol,
    ) -> tuple[list[Edge], dict[str, Symbol]]:
        edges: list[Edge] = []
        bindings: dict[str, Symbol] = {}

        for node in root.children:
            if node.type not in {"import_statement", "import_from_statement"}:
                continue
            statement = self._node_text(node, source_bytes).strip()
            if node.type == "import_from_statement":
                module_name = self._node_text(node.child_by_field_name("module_name"), source_bytes).strip()
                target_path = self._resolve_python_module_path(absolute_path, project_path, module_name)
                target_module = self._module_symbol_for_path(target_path, project_path)
                if target_module is None:
                    continue
                edges.append(
                    Edge(
                        source_sid=module_symbol.symbol_id,
                        target_sid=target_module.symbol_id,
                        type="IMPORTS",
                        line=node.start_point[0] + 1,
                    )
                )
                if " import " not in statement:
                    continue
                target_symbols = self.parse_file(str(target_path), project_path)
                names_part = statement.split(" import ", 1)[1].strip().strip("()")
                for raw_name in [part.strip() for part in names_part.split(",") if part.strip()]:
                    imported_name, _, alias_name = raw_name.partition(" as ")
                    binding_name = alias_name.strip() or imported_name.strip()
                    resolved = self._find_named_symbol(target_symbols, imported_name.strip())
                    if resolved is not None:
                        bindings[binding_name] = resolved
                continue

            imported_part = statement.removeprefix("import ").strip()
            for raw_name in [part.strip() for part in imported_part.split(",") if part.strip()]:
                module_name, _, alias_name = raw_name.partition(" as ")
                target_path = self._resolve_python_module_path(absolute_path, project_path, module_name.strip())
                target_module = self._module_symbol_for_path(target_path, project_path)
                if target_module is None:
                    continue
                edges.append(
                    Edge(
                        source_sid=module_symbol.symbol_id,
                        target_sid=target_module.symbol_id,
                        type="IMPORTS",
                        line=node.start_point[0] + 1,
                    )
                )
                bindings[alias_name.strip() or module_name.strip().split(".")[-1]] = target_module

        return edges, bindings

    def _collect_javascript_imports(
        self,
        absolute_path: str,
        root: Node,
        source_bytes: bytes,
        project_path: str,
        module_symbol: Symbol,
    ) -> tuple[list[Edge], dict[str, Symbol]]:
        edges: list[Edge] = []
        bindings: dict[str, Symbol] = {}

        for node in root.children:
            if node.type != "import_statement":
                continue
            statement = self._node_text(node, source_bytes).strip().rstrip(";")
            if " from " not in statement:
                continue

            clause_text, source_text = statement.removeprefix("import ").split(" from ", 1)
            module_spec = source_text.strip().strip("'\"")
            target_path = self._resolve_javascript_module_path(absolute_path, project_path, module_spec)
            target_module = self._module_symbol_for_path(target_path, project_path)
            if target_module is None:
                continue

            edges.append(
                Edge(
                    source_sid=module_symbol.symbol_id,
                    target_sid=target_module.symbol_id,
                    type="IMPORTS",
                    line=node.start_point[0] + 1,
                )
            )

            target_symbols = self.parse_file(str(target_path), project_path)
            clause_text = clause_text.strip()
            if clause_text.startswith("{") and clause_text.endswith("}"):
                for raw_name in [part.strip() for part in clause_text[1:-1].split(",") if part.strip()]:
                    imported_name, _, alias_name = raw_name.partition(" as ")
                    binding_name = alias_name.strip() or imported_name.strip()
                    resolved = self._find_named_symbol(target_symbols, imported_name.strip())
                    if resolved is not None:
                        bindings[binding_name] = resolved
            elif clause_text.startswith("* as "):
                bindings[clause_text.removeprefix("* as ").strip()] = target_module

        return edges, bindings

    def _extract_python_relation_edges(
        self,
        root: Node,
        source_bytes: bytes,
        symbols: list[Symbol],
        import_bindings: dict[str, Symbol],
    ) -> list[Edge]:
        symbols_by_qualified = {symbol.qualified_name: symbol for symbol in symbols}
        symbols_by_simple = self._symbols_by_simple_name(symbols)
        edges: list[Edge] = []

        def visit(node: Node, containers: list[str]) -> None:
            if node.type != "class_definition":
                for child in node.children:
                    visit(child, containers)
                return

            class_name = self._node_text(node.child_by_field_name("name"), source_bytes)
            qualified_name = ".".join([*containers, class_name]) if containers else class_name
            class_symbol = symbols_by_qualified.get(qualified_name)
            if class_symbol is not None:
                for child in node.children:
                    if child.type != "argument_list":
                        continue
                    for base_name in self._python_argument_names(child, source_bytes):
                        target = self._resolve_target(
                            base_name,
                            containers,
                            symbols_by_qualified,
                            symbols_by_simple,
                            import_bindings,
                        )
                        if target is None:
                            continue
                        edges.append(
                            Edge(
                                source_sid=class_symbol.symbol_id,
                                target_sid=target.symbol_id,
                                type="EXTENDS",
                                line=node.start_point[0] + 1,
                            )
                        )
            next_containers = [*containers, class_name] if class_name else containers
            for child in node.children:
                visit(child, next_containers)

        visit(root, [])
        return edges

    def _extract_javascript_relation_edges(
        self,
        root: Node,
        source_bytes: bytes,
        symbols: list[Symbol],
        import_bindings: dict[str, Symbol],
    ) -> list[Edge]:
        symbols_by_qualified = {symbol.qualified_name: symbol for symbol in symbols}
        symbols_by_simple = self._symbols_by_simple_name(symbols)
        edges: list[Edge] = []

        def visit(node: Node, containers: list[str]) -> None:
            if node.type != "class_declaration":
                for child in node.children:
                    visit(child, containers)
                return

            class_name = self._node_text(node.child_by_field_name("name"), source_bytes)
            qualified_name = ".".join([*containers, class_name]) if containers else class_name
            class_symbol = symbols_by_qualified.get(qualified_name)
            if class_symbol is not None:
                for child in node.children:
                    if child.type != "class_heritage":
                        continue
                    for heritage in child.children:
                        edge_type = None
                        if heritage.type == "extends_clause":
                            edge_type = "EXTENDS"
                        if heritage.type == "implements_clause":
                            edge_type = "IMPLEMENTS"
                        if edge_type is None:
                            continue
                        for target_name in self._identifier_names(heritage, source_bytes):
                            target = self._resolve_target(
                                target_name,
                                containers,
                                symbols_by_qualified,
                                symbols_by_simple,
                                import_bindings,
                            )
                            if target is None:
                                continue
                            edges.append(
                                Edge(
                                    source_sid=class_symbol.symbol_id,
                                    target_sid=target.symbol_id,
                                    type=edge_type,
                                    line=heritage.start_point[0] + 1,
                                )
                            )
            next_containers = [*containers, class_name] if class_name else containers
            for child in node.children:
                visit(child, next_containers)

        visit(root, [])
        return edges

    def _extract_call_edges(
        self,
        root: Node,
        source_bytes: bytes,
        symbols: list[Symbol],
        import_bindings: dict[str, Symbol],
        *,
        python: bool,
    ) -> list[Edge]:
        symbols_by_qualified = {symbol.qualified_name: symbol for symbol in symbols}
        symbols_by_simple = self._symbols_by_simple_name(symbols)
        edges: dict[tuple[str, str, str], Edge] = {}
        call_type = "call" if python else "call_expression"
        function_types = {"function_definition"} if python else {
            "function_declaration",
            "method_definition",
            "variable_declarator",
        }

        def add_edge(source_symbol: Symbol, raw_name: str, line: int, containers: list[str]) -> None:
            target = self._resolve_target(
                raw_name,
                containers,
                symbols_by_qualified,
                symbols_by_simple,
                import_bindings,
            )
            if target is None or target.symbol_id == source_symbol.symbol_id:
                return
            key = (source_symbol.symbol_id, target.symbol_id, "CALLS")
            edges.setdefault(
                key,
                Edge(
                    source_sid=source_symbol.symbol_id,
                    target_sid=target.symbol_id,
                    type="CALLS",
                    line=line,
                ),
            )

        def walk_calls(node: Node, source_symbol: Symbol, containers: list[str]) -> None:
            if node.type == call_type:
                callee_node = node.children[0] if python else node.child_by_field_name("function")
                callee_name = self._extract_callee_name(callee_node, source_bytes, python=python)
                add_edge(source_symbol, callee_name, node.start_point[0] + 1, containers)
            for child in node.children:
                walk_calls(child, source_symbol, containers)

        def visit(node: Node, containers: list[str]) -> None:
            if node.type == ("class_definition" if python else "class_declaration"):
                class_name = self._node_text(node.child_by_field_name("name"), source_bytes)
                next_containers = [*containers, class_name] if class_name else containers
                for child in node.children:
                    visit(child, next_containers)
                return

            if node.type in function_types:
                name = self._function_name(node, source_bytes, python=python)
                qualified_name = ".".join([*containers, name]) if name and containers else name
                source_symbol = symbols_by_qualified.get(qualified_name) if qualified_name else None
                if source_symbol is not None:
                    walk_calls(node, source_symbol, containers)
                next_containers = [*containers, name] if name else containers
                for child in node.children:
                    visit(child, next_containers)
                return

            for child in node.children:
                visit(child, containers)

        visit(root, [])
        return list(edges.values())

    @staticmethod
    def _collect_contains_edges(symbols: list[Symbol]) -> list[Edge]:
        symbols_by_qualified = {symbol.qualified_name: symbol for symbol in symbols}
        module_symbol = next((symbol for symbol in symbols if symbol.kind == "module"), None)
        if module_symbol is None:
            return []

        edges: list[Edge] = []
        for symbol in symbols:
            if symbol.symbol_id == module_symbol.symbol_id:
                continue
            if "." not in symbol.qualified_name:
                edges.append(
                    Edge(
                        source_sid=module_symbol.symbol_id,
                        target_sid=symbol.symbol_id,
                        type="CONTAINS",
                        line=symbol.line,
                    )
                )
                continue

            container_name = symbol.qualified_name.rsplit(".", 1)[0]
            container_symbol = symbols_by_qualified.get(container_name)
            if container_symbol is None:
                continue
            edges.append(
                Edge(
                    source_sid=container_symbol.symbol_id,
                    target_sid=symbol.symbol_id,
                    type="CONTAINS",
                    line=symbol.line,
                )
            )
        return edges

    @staticmethod
    def _dedupe_edges(edges: list[Edge]) -> list[Edge]:
        deduped: dict[tuple[str, str, str], Edge] = {}
        for edge in edges:
            deduped.setdefault((edge.source_sid, edge.target_sid, edge.type), edge)
        return list(deduped.values())

    @staticmethod
    def _node_text(node: Node | None, source_bytes: bytes) -> str:
        if node is None:
            return ""
        return source_bytes[node.start_byte : node.end_byte].decode("utf-8")

    def _function_name(self, node: Node, source_bytes: bytes, *, python: bool) -> str:
        if node.type == "variable_declarator":
            return self._node_text(node.child_by_field_name("name"), source_bytes)
        return self._node_text(node.child_by_field_name("name"), source_bytes)

    def _extract_callee_name(self, node: Node | None, source_bytes: bytes, *, python: bool) -> str:
        if node is None:
            return ""
        if python:
            if node.type == "identifier":
                return self._node_text(node, source_bytes)
            if node.type == "attribute":
                prefix = self._node_text(node.child_by_field_name("object"), source_bytes)
                suffix = self._node_text(node.child_by_field_name("attribute"), source_bytes)
                return f"{prefix}.{suffix}" if prefix and suffix else suffix
            return ""

        if node.type in {"identifier", "property_identifier"}:
            return self._node_text(node, source_bytes)
        if node.type == "member_expression":
            prefix = self._node_text(node.child_by_field_name("object"), source_bytes)
            suffix = self._node_text(node.child_by_field_name("property"), source_bytes)
            return f"{prefix}.{suffix}" if prefix and suffix else suffix
        return ""

    def _resolve_target(
        self,
        raw_name: str,
        containers: list[str],
        symbols_by_qualified: dict[str, Symbol],
        symbols_by_simple: dict[str, list[Symbol]],
        import_bindings: dict[str, Symbol],
    ) -> Symbol | None:
        if not raw_name:
            return None
        if raw_name in import_bindings:
            return import_bindings[raw_name]

        if raw_name.startswith(("self.", "this.")) and containers:
            method_name = raw_name.split(".", 1)[1]
            class_name = containers[0]
            candidate = symbols_by_qualified.get(f"{class_name}.{method_name}")
            if candidate is not None:
                return candidate
            raw_name = method_name

        if raw_name in symbols_by_qualified:
            return symbols_by_qualified[raw_name]

        if containers:
            candidate = symbols_by_qualified.get(".".join([*containers, raw_name]))
            if candidate is not None:
                return candidate
            candidate = symbols_by_qualified.get(f"{containers[0]}.{raw_name}")
            if candidate is not None:
                return candidate

        matches = symbols_by_simple.get(raw_name, [])
        if len(matches) == 1:
            return matches[0]
        top_level = [symbol for symbol in matches if "." not in symbol.qualified_name]
        if len(top_level) == 1:
            return top_level[0]
        return None

    @staticmethod
    def _symbols_by_simple_name(symbols: list[Symbol]) -> dict[str, list[Symbol]]:
        results: dict[str, list[Symbol]] = {}
        for symbol in symbols:
            results.setdefault(symbol.name, []).append(symbol)
        return results

    @staticmethod
    def _identifier_names(node: Node, source_bytes: bytes) -> list[str]:
        names: list[str] = []
        for child in node.children:
            if child.type in {"identifier", "type_identifier", "property_identifier"}:
                names.append(source_bytes[child.start_byte : child.end_byte].decode("utf-8"))
        return names

    @staticmethod
    def _python_argument_names(node: Node, source_bytes: bytes) -> list[str]:
        names: list[str] = []
        for child in node.children:
            if child.type in {"identifier", "attribute"}:
                names.append(source_bytes[child.start_byte : child.end_byte].decode("utf-8"))
        return names

    def _find_named_symbol(self, symbols: list[Symbol], name: str) -> Symbol | None:
        for symbol in symbols:
            if symbol.kind == "module":
                continue
            if symbol.name == name or symbol.qualified_name == name:
                return symbol
        return None

    def _module_symbol(self, rel_path: str, project_path: str, language_name: str) -> Symbol:
        return Symbol(
            name=Path(rel_path).stem,
            qualified_name=rel_path,
            kind="module",
            file=rel_path,
            line=1,
            language=self._public_language(language_name),
            project_path=project_path,
        )

    def _module_symbol_for_path(self, target_path: Path | None, project_path: str) -> Symbol | None:
        if target_path is None:
            return None
        language_name = self.SUPPORTED_V1.get(target_path.suffix.lower())
        if language_name is None:
            return None
        rel_path = target_path.resolve().relative_to(Path(project_path).resolve()).as_posix()
        return self._module_symbol(rel_path, project_path, language_name)

    def _resolve_python_module_path(
        self,
        current_file: str,
        project_path: str,
        module_name: str,
    ) -> Path | None:
        project_root = Path(project_path).resolve()
        current_parent = Path(current_file).resolve().parent
        stripped = module_name.strip()
        if not stripped:
            return None

        leading_dots = len(stripped) - len(stripped.lstrip("."))
        module_suffix = stripped.lstrip(".").replace(".", os.sep)
        base_dir = current_parent if leading_dots else project_root
        for _ in range(max(leading_dots - 1, 0)):
            base_dir = base_dir.parent

        candidates: list[Path] = []
        if module_suffix:
            candidates.append((base_dir / module_suffix).with_suffix(".py"))
            candidates.append(base_dir / module_suffix / "__init__.py")
        else:
            candidates.append(base_dir / "__init__.py")

        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()
        return None

    def _resolve_javascript_module_path(
        self,
        current_file: str,
        project_path: str,
        module_spec: str,
    ) -> Path | None:
        if not module_spec.startswith("."):
            return None

        current_parent = Path(current_file).resolve().parent
        project_root = Path(project_path).resolve()
        base_candidate = (current_parent / module_spec).resolve()
        candidates: list[Path] = []

        if base_candidate.suffix:
            candidates.append(base_candidate)
        else:
            for ext in (".ts", ".tsx", ".js", ".jsx"):
                candidates.append(base_candidate.with_suffix(ext))
            for ext in (".ts", ".tsx", ".js", ".jsx"):
                candidates.append(base_candidate / f"index{ext}")

        for candidate in candidates:
            if not candidate.exists():
                continue
            try:
                candidate.relative_to(project_root)
            except ValueError:
                continue
            return candidate.resolve()
        return None

    @staticmethod
    def _public_language(language_name: str) -> str:
        return "typescript" if language_name in {"typescript", "tsx"} else language_name
