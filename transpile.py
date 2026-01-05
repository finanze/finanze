"""
This file is an LLM-generated utility script.

It translates Python domain models (entities, enums, type aliases, and use case interfaces)
from the finanze project into TypeScript types for use in the mobile frontend.

It can also transpile infrastructure repository `queries.py` modules (primarily enums)
into the mobile `services/database/repositories/queries/core` folder.
"""

import ast
import importlib.util
import inspect
import os
import re
import sys
from pathlib import Path

# Add finanze to PYTHONPATH
finanze_path = Path(__file__).parent / "finanze"
if str(finanze_path) not in sys.path:
    sys.path.insert(0, str(finanze_path))

# Supertypes to ignore when generating `extends` clauses
# (e.g. BaseData is just a shared Python marker/base and shouldn't leak into TS)
IGNORED_SUPERTYPES: set[str] = {"BaseData"}

# When True, all generated use case function types are treated as async and return Promise<...>
FORCE_ASYNC_USE_CASES: bool = True

# When True, all generated port interface methods are treated as async and return Promise<...>
FORCE_ASYNC_PORT_METHODS: bool = True

# Collected per-use-case import alias mappings (module-qualified name -> {symbol: alias})
USE_CASE_IMPORT_ALIASES: dict[str, dict[str, str]] = {}

# Output roots (filled in __main__) used to compute relative TS imports
DOMAIN_TS_OUT_DIR: Path | None = None
USE_CASE_TS_OUT_DIR: Path | None = None
PORTS_TS_OUT_DIR: Path | None = None


def get_declarations_in_order(file_path: Path) -> list[tuple[str, str]]:
    """Return a list of (kind, name) for top-level declarations in source order.

    kind is one of: 'class', 'alias'.
    """
    with open(file_path, "r") as f:
        tree = ast.parse(f.read())

    decls: list[tuple[str, str]] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            decls.append(("class", node.name))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                if isinstance(node.value, ast.Subscript) or (
                    isinstance(node.value, ast.BinOp)
                    and isinstance(node.value.op, ast.BitOr)
                ):
                    decls.append(("alias", target.id))
    return decls


def get_defined_classes(file_path: Path) -> list[str]:
    """Extract class names defined in the file, preserving source order."""
    with open(file_path, "r") as f:
        tree = ast.parse(f.read())

    defined_classes: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            defined_classes.append(node.name)
    return defined_classes


def get_type_aliases(file_path: Path) -> list[str]:
    """Extract module-level type alias names, preserving source order."""
    with open(file_path, "r") as f:
        tree = ast.parse(f.read())

    type_aliases: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                # Accept a few common alias shapes:
                # - typing generics: X = list[Y] / dict[K, V] (ast.Subscript)
                # - PEP604 unions: X = A | B | C (ast.BinOp with BitOr)
                if isinstance(node.value, ast.Subscript) or (
                    isinstance(node.value, ast.BinOp)
                    and isinstance(node.value.op, ast.BitOr)
                ):
                    type_aliases.append(target.id)
    return type_aliases


def collect_type_dependencies(
    type_hint, current_module: str, defined_in_file: set
) -> set:
    """Recursively collect all type dependencies that need to be imported"""

    dependencies = set()

    # Handle string annotations (from __future__ import annotations)
    if isinstance(type_hint, str):
        s = type_hint.strip().strip('"').strip("'")

        # NOTE: Don't eagerly add Dezimal here.
        # - Use cases normally resolve real objects through typing.get_type_hints(), and
        #   Dezimal will be imported via the non-string branch below.
        # - Eager-importing it from string content causes unused imports in TS files.

        # Drill into Optional/List/Dict and union strings
        # We only care about identifiers that are not primitives.
        # Heuristic: extract tokens that look like type names.
        tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", s)
        primitives = {
            "str",
            "int",
            "float",
            "bool",
            "None",
            "Optional",
            "List",
            "Dict",
            "Any",
            "bytes",
            "type",
        }
        for tok in tokens:
            if tok in primitives:
                continue
            if tok == "Dezimal":
                continue
            # UUID/datetime/date/Path are mapped to primitives
            if tok in {"UUID", "datetime", "date", "Path"}:
                continue
            # If it's defined in file, skip
            if tok in defined_in_file:
                continue
            # For same-module classes we don't import; others will be visited elsewhere
            # We can’t reliably resolve module from string here, so do nothing.
        return dependencies

    # Skip if it's None or a basic type
    if type_hint in (int, float, str, bool, type(None), list, dict, bytes, type):
        return dependencies

    type_str = str(type_hint)

    # Track Dezimal as a special dependency
    if "Dezimal" in type_str:
        dependencies.add(("Dezimal", "@/domain/dezimal"))
        return dependencies

    # Skip custom types we convert to primitives (but not Dezimal anymore)
    # Use more specific patterns to avoid matching class names containing these substrings
    skip_patterns = [
        "uuid.UUID",
        "UUID>",
        "datetime.datetime",
        "datetime.date",
        "pathlib.Path",
        "IOBase",
        "typing.Any",
    ]
    if any(x in type_str for x in skip_patterns):
        return dependencies

    # Handle generic types (Optional, List, Dict, Union)
    if hasattr(type_hint, "__origin__"):
        args = getattr(type_hint, "__args__", ())
        for arg in args:
            if arg is not type(None):  # Skip None in Optional
                dependencies.update(
                    collect_type_dependencies(arg, current_module, defined_in_file)
                )
        return dependencies

    # Handle Enum and class types
    if inspect.isclass(type_hint):
        # Add if it's from domain or application ports.
        if hasattr(type_hint, "__module__") and (
            type_hint.__module__.startswith("domain.")
            or type_hint.__module__.startswith("finanze.domain")
            or type_hint.__module__.startswith("application.")
            or type_hint.__module__.startswith("finanze.application")
        ):
            type_module = type_hint.__module__
            # Normalize to domain.xxx / application.xxx format
            if type_module.startswith("finanze."):
                type_module = type_module[len("finanze.") :]
            type_name = type_hint.__name__

            # Don't import if it's defined in the current file
            if type_name not in defined_in_file:
                # Don't import from the same module
                if type_module != current_module:
                    dependencies.add((type_name, type_module))

    return dependencies


def _ts_module_relpath(from_dir: Path, to_file: Path) -> str:
    """Return a TS import specifier (./foo or ../bar/baz) from one directory to a .ts file."""
    rel = (
        to_file.relative_to(from_dir)
        if to_file.is_absolute() and to_file.is_relative_to(from_dir)
        else None
    )
    if rel is None:
        rel = Path(os.path.relpath(to_file, start=from_dir))
    spec = rel.as_posix()
    if spec.endswith(".ts"):
        spec = spec[:-3]
    if not spec.startswith("."):
        spec = f"./{spec}"
    return spec


def _module_to_ts_file(module: str) -> Path | None:
    """Map a python module to the generated TS file path."""
    if module == "@/domain/dezimal":
        return None

    parts = module.split(".")
    if len(parts) < 2:
        return None

    # Domain
    if parts[0] == "domain":
        # domain.use_cases.<name>
        if len(parts) >= 3 and parts[1] == "use_cases":
            if USE_CASE_TS_OUT_DIR is None:
                return None
            file_stem = parts[2]
            camel = re.sub(r"_([a-z])", lambda m: m.group(1).upper(), file_stem)
            return USE_CASE_TS_OUT_DIR / f"{camel}.ts"

        # domain.<name>
        if DOMAIN_TS_OUT_DIR is None:
            return None
        file_stem = parts[1]
        camel = re.sub(r"_([a-z])", lambda m: m.group(1).upper(), file_stem)
        return DOMAIN_TS_OUT_DIR / f"{camel}.ts"

    # Application ports
    if parts[0] == "application" and len(parts) >= 3 and parts[1] == "ports":
        # application.ports.<file>
        ports_out_dir = PORTS_TS_OUT_DIR
        if ports_out_dir is None:
            return None
        file_stem = parts[2]
        camel = re.sub(r"_([a-z])", lambda m: m.group(1).upper(), file_stem)
        return ports_out_dir / f"{camel}.ts"

    return None


def generate_typescript_imports(
    dependencies: set,
    is_use_case: bool = False,
    import_aliases: dict[str, str] | None = None,
    from_dir: Path | None = None,
) -> str:
    """Generate TypeScript import statements from dependencies.

    - For domain dependencies we compute the relative path to the generated module file.
    - For Dezimal we keep the fixed alias import path.

    import_aliases maps original imported symbol -> alias to use in TS import.
    """
    if not dependencies:
        return ""

    import_aliases = import_aliases or {}

    # Default `from_dir` to the appropriate output root
    if from_dir is None:
        from_dir = USE_CASE_TS_OUT_DIR if is_use_case else DOMAIN_TS_OUT_DIR

    imports_by_spec: dict[str, set[str]] = {}

    for type_name, module in dependencies:
        if module == "@/domain/dezimal":
            spec = "@/domain/dezimal"

        # Ports and use cases should consume all domain types via the '@/domain' barrel
        elif (
            from_dir in {PORTS_TS_OUT_DIR, USE_CASE_TS_OUT_DIR}
            and isinstance(module, str)
            and module.startswith("domain.")
        ):
            spec = "@/domain"

        else:
            ts_file = _module_to_ts_file(module)
            if ts_file is None:
                continue
            if from_dir is None:
                continue
            spec = _ts_module_relpath(from_dir, ts_file)

        imports_by_spec.setdefault(spec, set()).add(type_name)

    import_lines = []
    for spec in sorted(imports_by_spec.keys()):
        types = sorted(imports_by_spec[spec])
        parts = []
        for t in types:
            alias = import_aliases.get(t)
            if alias and alias != t:
                parts.append(f"{t} as {alias}")
            else:
                parts.append(t)
        types_str = ", ".join(parts)
        import_lines.append(f"import {{ {types_str} }} from '{spec}';")

    return "\n".join(import_lines)


def python_type_to_typescript(
    type_hint, module_name: str, defined_in_file: set = None
) -> str:
    """Convert Python type hints to TypeScript types"""
    import typing
    from enum import Enum

    if defined_in_file is None:
        defined_in_file = set()

    def _is_record_key_ts(ts_key: str) -> bool:
        """Whether a TS type can be used as a Record<K, V> key.

        Record keys must be property keys: string | number | symbol.
        """
        k = ts_key.strip()
        return k in {"string", "number", "symbol"}

    def _is_enum_type_hint(t) -> bool:
        try:
            return inspect.isclass(t) and issubclass(t, Enum)
        except Exception:
            return False

    def _dict_ts(key_ts: str, val_ts: str, key_hint=None) -> str:
        """Emit Record or Map depending on key type."""
        is_enum = _is_enum_type_hint(key_hint)
        if _is_record_key_ts(key_ts) or is_enum:
            if is_enum:
                return f"Partial<Record<{key_ts}, {val_ts}>>"
            else:
                return f"Record<{key_ts}, {val_ts}>"
        return f"Map<{key_ts}, {val_ts}>"

    # Convert type to string for analysis
    type_str = str(type_hint)

    # Handle cases where upstream code injects custom stringified optional types
    # like: "SomeType  None" (note the double space) instead of a real typing.Union.
    if "  None" in type_str:
        parts = [p for p in type_str.split("  ") if p.strip()]
        ts_parts = []
        for p in parts:
            ts_parts.append(
                python_type_to_typescript(p.strip(), module_name, defined_in_file)
            )
        # ensure null is present
        if "null" not in ts_parts:
            ts_parts.append("null")
        return " | ".join(ts_parts)

    # Handle string forward references / future annotations
    if isinstance(type_hint, str):
        return python_annotation_str_to_ts(type_hint, module_name, defined_in_file)

    # Handle basic types FIRST (these are exact type checks, not string matching)
    if type_hint in (int, float):
        return "number"
    if type_hint is str:
        return "string"
    if type_hint is bool:
        return "boolean"
    if type_hint is type(None) or type_str == "None":
        return "null"
    if type_hint is bytes or type_str == "<class 'bytes'>" or type_str == "bytes":
        return "Uint8Array"
    if type_hint is type or type_str == "<class 'type'>" or type_str == "type":
        return "string"

    # Handle bare list and dict (without type parameters)
    if type_hint is list or type_str == "<class 'list'>" or type_str == "list":
        return "any[]"
    if type_hint is dict or type_str == "<class 'dict'>" or type_str == "dict":
        return "Record<string, any>"

    # Handle Any
    if "typing.Any" in type_str or (hasattr(typing, "Any") and type_hint is typing.Any):
        return "any"

    # Handle Optional/Union/List/Dict generics BEFORE string pattern matching
    # This ensures list[UUID] is handled as a list, not matched by "uuid.UUID" pattern
    if hasattr(type_hint, "__origin__"):
        origin = type_hint.__origin__
        args = getattr(type_hint, "__args__", ())

        if origin is typing.Union:
            # Optional[X] is Union[X, None]
            if len(args) == 2 and type(None) in args:
                non_none = [a for a in args if a is not type(None)][0]
                return f"{python_type_to_typescript(non_none, module_name, defined_in_file)} | null"

            # Union of file-like types -> Uint8Array
            non_none_args = [a for a in args if a is not type(None)]
            if len(non_none_args) >= 1 and all(
                _is_file_like_type(a) for a in non_none_args
            ):
                return "Uint8Array"

            return " | ".join(
                python_type_to_typescript(a, module_name, defined_in_file) for a in args
            )

        if origin is list or (hasattr(typing, "List") and origin is typing.List):
            if args:
                return f"{python_type_to_typescript(args[0], module_name, defined_in_file)}[]"
            return "any[]"

        if origin is dict or (hasattr(typing, "Dict") and origin is typing.Dict):
            if len(args) == 2:
                key_type = python_type_to_typescript(
                    args[0], module_name, defined_in_file
                )
                val_type = python_type_to_typescript(
                    args[1], module_name, defined_in_file
                )
                return _dict_ts(key_type, val_type, key_hint=args[0])
            return "Record<string, any>"

    # Handle Enum types
    if inspect.isclass(type_hint) and issubclass(type_hint, Enum):
        return type_hint.__name__

    # Handle UUID/datetime/date/Path as strings
    from uuid import UUID as UUIDType
    from datetime import datetime as DateTimeType, date as DateType
    from pathlib import Path as PathType

    if inspect.isclass(type_hint) and type_hint is UUIDType:
        return "string"
    if inspect.isclass(type_hint) and (
        type_hint is DateTimeType or type_hint is DateType
    ):
        return "string"
    if inspect.isclass(type_hint) and type_hint is PathType:
        return "string"

    # Handle Dezimal
    try:
        from domain.dezimal import Dezimal as dezimal_type
    except Exception:
        dezimal_type = None

    if (
        dezimal_type is not None
        and inspect.isclass(type_hint)
        and type_hint is dezimal_type
    ):
        return "Dezimal"

    # Handle other classes
    if inspect.isclass(type_hint):
        if hasattr(type_hint, "__module__") and (
            type_hint.__module__.startswith("finanze.domain")
            or type_hint.__module__.startswith("domain.")
        ):
            return type_hint.__name__
        return type_hint.__name__

    # String pattern fallbacks
    if "uuid.UUID" in type_str or type_str == "<class 'uuid.UUID'>":
        return "string"
    if "Dezimal" in type_str:
        return "Dezimal"
    if "datetime.datetime" in type_str or "datetime.date" in type_str:
        return "string"
    if "pathlib.Path" in type_str or type_str == "Path":
        return "string"
    if "IOBase" in type_str or "typing.IO" in type_str:
        return "Uint8Array"

    return "any"


def _is_file_like_type(type_hint) -> bool:
    """Check if a type is a file-like type (IO, IOBase)."""
    type_str = str(type_hint)
    return "IOBase" in type_str or "typing.IO" in type_str


def generate_port_interface(
    cls, module_name: str, dependencies: set
) -> tuple[str, set]:
    """Generate a TypeScript interface for an application port abstract class."""
    import typing

    port_name = cls.__name__

    # Names imported from domain.* in the port module (includes type aliases like EntityCredentials).
    imported_domain_names: set[str] = set()
    # Best-effort mapping alias_name -> alias_object as imported into the port module.
    imported_domain_alias_objects: dict[str, object] = {}

    def _load_domain_alias_structural_ts() -> dict[str, str]:
        """Load `export type X = ...` definitions from generated domain core TS.

        This allows ports to always use the alias name (X) even if the inferred TS type
        expands to the alias structural definition.
        """
        out: dict[str, str] = {}
        if DOMAIN_TS_OUT_DIR is None:
            return out
        try:
            for f in DOMAIN_TS_OUT_DIR.glob("*.ts"):
                if f.name == "index.ts":
                    continue
                txt = f.read_text(encoding="utf-8")
                # single-line type aliases are expected in our generator
                for m in re.finditer(
                    r"^export type\s+(\w+)\s*=\s*(.+)$", txt, flags=re.M
                ):
                    name = m.group(1)
                    rhs = m.group(2).strip().rstrip(";")
                    out[name] = rhs
        except Exception:
            return out
        return out

    domain_alias_ts_definitions: dict[str, str] = _load_domain_alias_structural_ts()

    # Strong fallback: add domain imports declared in the port module itself.
    # This avoids missing imports when runtime type-hint resolution fails.
    try:
        src_path = Path(inspect.getsourcefile(cls) or "")
        if src_path.exists():
            tree = ast.parse(src_path.read_text())
            for node in tree.body:
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.module
                    and node.module.startswith("domain.")
                ):
                    for alias in node.names:
                        imported_domain_names.add(alias.name)
                        # Dezimal keeps its dedicated import
                        if node.module == "domain.dezimal" and alias.name == "Dezimal":
                            dependencies.add(("Dezimal", "@/domain/dezimal"))
                        else:
                            dependencies.add((alias.name, node.module))

        # Resolve imported names to objects from the port module.
        port_mod = sys.modules.get(cls.__module__)
        if port_mod is not None:
            for name in imported_domain_names:
                if hasattr(port_mod, name):
                    imported_domain_alias_objects[name] = getattr(port_mod, name)
    except Exception:
        pass

    def _ts_type_for_port_hint(raw_annot, resolved_hint) -> str:
        """TS type for a port parameter/return.

        Prefer imported alias names when possible, even if resolved hint is the underlying builtin.
        """
        # 1) If raw annotation is already a name string and imported, preserve it.
        if isinstance(raw_annot, str) and raw_annot in imported_domain_names:
            return raw_annot

        # 2) If raw annotation is a class/type and its name is imported, preserve its name.
        if (
            inspect.isclass(raw_annot)
            and getattr(raw_annot, "__name__", None) in imported_domain_names
        ):
            return raw_annot.__name__

        # 3) If resolved hint exactly equals an imported alias object, preserve alias name.
        for alias_name, alias_obj in imported_domain_alias_objects.items():
            if resolved_hint is alias_obj:
                return alias_name

        # 4) Optional[Alias] / Union[Alias, None]
        if (
            hasattr(resolved_hint, "__origin__")
            and resolved_hint.__origin__ is typing.Union
        ):
            args = getattr(resolved_hint, "__args__", ())
            non_none = [a for a in args if a is not type(None)]
            if len(non_none) == 1:
                inner = non_none[0]
                for alias_name, alias_obj in imported_domain_alias_objects.items():
                    if inner is alias_obj:
                        return f"{alias_name} | null"

        # Fallback
        if isinstance(resolved_hint, str):
            return python_annotation_str_to_ts(resolved_hint, module_name, set())
        return python_type_to_typescript(resolved_hint, module_name)

    def _apply_alias_deexpansion(ts_type: str) -> str:
        """Replace structural shapes with alias names for ports (only when alias is imported)."""
        base = ts_type.strip().rstrip(";")
        nullable = False
        if base.endswith("| null"):
            nullable = True
            base = base[: -len("| null")].strip()

        # Normalize whitespace inside generics so comparisons are stable.
        base_norm = re.sub(r"\s+", " ", base)

        def _strip_partial(s: str) -> str:
            s = s.strip()
            if s.startswith("Partial<") and s.endswith(">"):
                return s[len("Partial<") : -1].strip()
            return s

        # If a port imports some domain alias, and our inferred type matches that alias definition,
        # emit the alias name instead.
        for alias_name in imported_domain_names:
            rhs = domain_alias_ts_definitions.get(alias_name)
            if not rhs:
                continue

            rhs_norm = re.sub(r"\s+", " ", rhs.strip().rstrip(";"))

            # Exact match
            if base_norm == rhs_norm:
                return f"{alias_name} | null" if nullable else alias_name

            # Structural-equivalence normalization: consider `Partial<X>` equivalent to `X`.
            if (
                _strip_partial(rhs_norm) == base_norm
                or _strip_partial(base_norm) == rhs_norm
            ):
                return f"{alias_name} | null" if nullable else alias_name

        return ts_type

    lines: list[str] = [f"export interface {port_name} {{"]

    # Preserve method order as they appear in the class body
    method_nodes = []
    try:
        src_path = Path(inspect.getsourcefile(cls) or "")
        if src_path.exists():
            tree = ast.parse(src_path.read_text())
            for node in tree.body:
                if isinstance(node, ast.ClassDef) and node.name == port_name:
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            method_nodes.append(item.name)
                    break
    except Exception:
        method_nodes = []

    # Fallback: use class dict ordering
    if not method_nodes:
        method_nodes = [
            name
            for name, v in cls.__dict__.items()
            if inspect.isfunction(v) and not name.startswith("_")
        ]

    for method_name in method_nodes:
        method = getattr(cls, method_name, None)
        if method is None or not inspect.isfunction(method):
            continue

        # Resolve hints
        try:
            cls_module = sys.modules.get(cls.__module__)
            globalns = getattr(cls_module, "__dict__", {}) if cls_module else {}
            type_hints = typing.get_type_hints(method, globalns=globalns, localns={})
        except Exception:
            type_hints = {}

        sig = inspect.signature(method)

        params = []
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            raw_param_annot = param.annotation
            param_type = type_hints.get(param_name)
            if param_type is None:
                param_type = raw_param_annot

            if param_type == inspect.Parameter.empty:
                ts_type = "any"
            elif isinstance(param_type, str):
                ts_type = python_annotation_str_to_ts(param_type, module_name, set())
            else:
                ts_type = _ts_type_for_port_hint(raw_param_annot, param_type)

            ts_type = _apply_alias_deexpansion(ts_type)

            # Normalize any accidental whitespace-before-null from upstream stringified optionals.
            # Example: "PositionQueryRequest  None" -> "PositionQueryRequest | null"
            ts_type = re.sub(r"\s*\|\s*(?:\|\s*)*null\b", " | null", ts_type)
            ts_type = re.sub(r"(?<!\|)\s+null\b", " | null", ts_type)

            # Collect dependencies from both resolved hints and raw annotations.
            # This catches missed imports like BaseTx/Entity/etc.
            if raw_param_annot not in (inspect.Parameter.empty, None):
                dependencies.update(
                    collect_type_dependencies(raw_param_annot, module_name, set())
                )
            if param_type not in (inspect.Parameter.empty, None):
                dependencies.update(
                    collect_type_dependencies(param_type, module_name, set())
                )

            # Optional parameter if default exists
            optional = "?" if param.default is not inspect.Parameter.empty else ""

            camel_param = re.sub(r"_([a-z])", lambda m: m.group(1).upper(), param_name)
            params.append(f"{camel_param}{optional}: {ts_type}")

        # Return
        raw_return_annot = sig.return_annotation
        return_type = type_hints.get("return")
        if return_type is None:
            return_type = raw_return_annot

        if return_type == inspect.Signature.empty or return_type is None:
            ts_return = "void"
        else:
            ts_return = _ts_type_for_port_hint(raw_return_annot, return_type)

        ts_return = _apply_alias_deexpansion(ts_return)

        ts_return = re.sub(r"\s*\|\s*(?:\|\s*)*null\b", " | null", ts_return)
        ts_return = re.sub(r"(?<!\|)\s+null\b", " | null", ts_return)

        if raw_return_annot not in (inspect.Signature.empty, None):
            dependencies.update(
                collect_type_dependencies(raw_return_annot, module_name, set())
            )
        if return_type not in (inspect.Signature.empty, None):
            dependencies.update(
                collect_type_dependencies(return_type, module_name, set())
            )

        is_async = FORCE_ASYNC_PORT_METHODS
        if is_async:
            ts_return = f"Promise<{ts_return}>"

        camel_method = re.sub(r"_([a-z])", lambda m: m.group(1).upper(), method_name)
        lines.append(f"  {camel_method}({', '.join(params)}): {ts_return}")

    lines.append("}")
    return "\n".join(lines), dependencies


def generate_typescript_interface(
    cls, module_name: str, defined_in_file: set
) -> tuple[str, set]:
    """Generate a TypeScript interface from a Python dataclass and collect dependencies"""
    from enum import Enum
    import abc
    import typing
    import types

    dependencies = set()

    # Use cases
    if hasattr(cls, "execute") and isinstance(cls, abc.ABCMeta):
        return generate_use_case_type(cls, module_name, dependencies)

    # Application ports
    if (
        module_name.startswith("application.ports")
        and inspect.isclass(cls)
        and isinstance(cls, abc.ABCMeta)
    ):
        return generate_port_interface(cls, module_name, dependencies)

    # Unwrap our internal alias wrapper
    alias_name = getattr(cls, "__name__", None)
    underlying_hint = getattr(cls, "_type_hint", None)
    if underlying_hint is not None and alias_name:
        cls_for_alias = underlying_hint
        alias_type_name = alias_name
    else:
        cls_for_alias = cls
        alias_type_name = alias_name

    # Check if it's a type alias (not a class but a type hint)
    if not inspect.isclass(cls):
        # Handle typing-based aliases first (dict/list/Union etc)
        origin = getattr(cls_for_alias, "__origin__", None)
        if origin in (dict, typing.Dict):
            type_name = alias_type_name or getattr(
                cls_for_alias, "__name__", "UnknownType"
            )
            args = getattr(cls_for_alias, "__args__", ())
            if len(args) == 2:
                key_type = python_type_to_typescript(
                    args[0], module_name, defined_in_file
                )

                # If the value type is a same-file alias (like ProductPosition), use its alias name
                val_obj = args[1]
                mod_for_alias = sys.modules.get(module_name)
                if mod_for_alias is not None:
                    for alias in defined_in_file:
                        if (
                            hasattr(mod_for_alias, alias)
                            and getattr(mod_for_alias, alias) is val_obj
                        ):
                            val_type = alias
                            break
                    else:
                        val_type = python_type_to_typescript(
                            val_obj, module_name, defined_in_file
                        )
                else:
                    val_type = python_type_to_typescript(
                        val_obj, module_name, defined_in_file
                    )

                dependencies.update(
                    collect_type_dependencies(args[0], module_name, defined_in_file)
                )
                dependencies.update(
                    collect_type_dependencies(args[1], module_name, defined_in_file)
                )
                return (
                    f"export type {type_name} = Partial<Record<{key_type}, {val_type}>>",
                    dependencies,
                )
            return f"export type {type_name} = Record<string, any>", dependencies

        if origin is typing.Union:
            type_name = alias_type_name or getattr(
                cls_for_alias, "__name__", "UnknownType"
            )
            args = getattr(cls_for_alias, "__args__", ())
            union_parts = []
            for arg in args:
                ts_type = python_type_to_typescript(arg, module_name, defined_in_file)
                union_parts.append(ts_type)
                dependencies.update(
                    collect_type_dependencies(arg, module_name, defined_in_file)
                )
            union_str = " | ".join(union_parts)
            return f"export type {type_name} = {union_str}", dependencies

        # PEP604 union alias
        if isinstance(cls_for_alias, types.UnionType):
            type_name = alias_type_name or getattr(
                cls_for_alias, "__name__", "UnknownType"
            )
            args = getattr(cls_for_alias, "__args__", ())
            union_parts = []
            for arg in args:
                ts_type = python_type_to_typescript(arg, module_name, defined_in_file)
                union_parts.append(ts_type)
                dependencies.update(
                    collect_type_dependencies(arg, module_name, defined_in_file)
                )
            union_str = " | ".join(union_parts)
            return f"export type {type_name} = {union_str}", dependencies

        return (
            f"// Unable to generate type for {getattr(cls_for_alias, '__name__', 'Unknown')}\n",
            dependencies,
        )

    # Check if it's an enum FIRST (before annotations check, since enums don't have annotations)
    if inspect.isclass(cls) and issubclass(cls, Enum):
        lines = [f"export enum {cls.__name__} {{"]
        # Preserve original order of enum members
        for member in cls:
            v = member.value
            if isinstance(v, str):
                # Use template literals for multi-line SQL strings (common in queries.py)
                escaped = v.replace("`", "\\`")
                if "\n" in escaped or "\r" in escaped:
                    lines.append(f"  {member.name} = `{escaped}`,")
                else:
                    lines.append(f'  {member.name} = "{escaped}",')
            else:
                lines.append(f"  {member.name} = {repr(v)},")
        lines.append("}")
        return "\n".join(lines), dependencies

    # Determine if this class extends another domain class
    raw_base_names = [
        b.__name__ for b in getattr(cls, "__bases__", ()) if b is not object
    ]
    base_names = [b for b in raw_base_names if b not in IGNORED_SUPERTYPES]

    extends_clause = ""
    if base_names:
        # Use the first non-object non-ignored base.
        extends_clause = f" extends {base_names[0]}"
        # Dependency for base if not in same file
        if base_names[0] not in defined_in_file:
            base_obj = getattr(
                sys.modules.get(cls.__module__, None), base_names[0], None
            )
            if base_obj is not None and inspect.isclass(base_obj):
                dependencies.update(
                    collect_type_dependencies(base_obj, module_name, defined_in_file)
                )

    # If no annotations but we do have a non-ignored base class, emit an empty extending interface.
    if (
        not hasattr(cls, "__annotations__") or not cls.__annotations__
    ) and extends_clause:
        return f"export interface {cls.__name__}{extends_clause} {{}}", dependencies

    # If no annotations and no base (or only ignored bases), still emit an empty interface.
    if not hasattr(cls, "__annotations__") or not cls.__annotations__:
        return f"export interface {cls.__name__} {{}}", dependencies

    # Generate interface for dataclass
    lines = [f"export interface {cls.__name__}{extends_clause} {{"]

    annotations = cls.__annotations__

    # Best-effort: get dataclass field info to detect defaults (pydantic.dataclasses uses std dataclasses)
    try:
        import dataclasses

        dataclass_fields = {f.name: f for f in dataclasses.fields(cls)}
    except Exception:
        dataclass_fields = {}

    for field_name, field_type in annotations.items():
        camel_case_name = re.sub(r"_([a-z])", lambda m: m.group(1).upper(), field_name)

        # 1) Determine if the property should be optional in TS (`?`) based on Python default/default_factory
        has_default = False
        f = dataclass_fields.get(field_name)
        if f is not None:
            import dataclasses

            has_default = (f.default is not dataclasses.MISSING) or (
                f.default_factory is not dataclasses.MISSING
            )

        # 2) Determine if the *type* includes None (Optional) -> should include `| null`
        is_optional_type = False
        actual_type = field_type

        if isinstance(field_type, str):
            s = field_type.strip().strip('"').strip("'")
            if s.startswith("Optional[") and s.endswith("]"):
                is_optional_type = True
                actual_type = s[len("Optional[") : -1]
            elif "|" in s and ("None" in [p.strip() for p in s.split("|")]):
                is_optional_type = True
                # Keep full union and rely on string parser; but mark optional type.
                actual_type = field_type
        else:
            if (
                hasattr(field_type, "__origin__")
                and field_type.__origin__ is typing.Union
            ):
                args = getattr(field_type, "__args__", ())
                if type(None) in args:
                    is_optional_type = True

        # 3) Prefer alias name if this field matches a type alias exactly
        ts_type = None
        type_to_check = actual_type
        if not isinstance(type_to_check, str):
            for alias_name in defined_in_file:
                if hasattr(cls, "__module__"):
                    try:
                        module = sys.modules.get(cls.__module__)
                        if module and hasattr(module, alias_name):
                            alias_type = getattr(module, alias_name)
                            if type_to_check is alias_type:
                                ts_type = alias_name
                                break
                    except Exception:
                        pass

        if ts_type is None:
            ts_type = python_type_to_typescript(
                type_to_check, module_name, defined_in_file
            )

        # Ensure Optional[T] yields `T | null` in TS, irrespective of `?`
        if is_optional_type:
            parts = [p.strip() for p in ts_type.split("|")]
            if "null" not in parts:
                ts_type = f"{ts_type} | null"

        # Emit
        opt = "?" if has_default else ""
        lines.append(f"  {camel_case_name}{opt}: {ts_type}")

        # Dependencies should follow the final emitted TS type, not only the raw python annotation.
        # This prevents missing imports when annotations are strings and can't be resolved (e.g. Dezimal).
        if "Dezimal" in ts_type:
            dependencies.add(("Dezimal", "@/domain/dezimal"))
        else:
            dependencies.update(
                collect_type_dependencies(field_type, module_name, defined_in_file)
            )

    lines.append("}")
    return "\n".join(lines), dependencies


def generate_use_case_type(cls, module_name: str, dependencies: set) -> tuple[str, set]:
    """Generate a TypeScript interface for a use case class.

    Example:
      export interface GetBackups {
        execute(request: BackupsInfoRequest): Promise<FullBackupsInfo>
      }
    """
    import typing

    # Get the execute method
    execute_method = getattr(cls, "execute", None)
    if not execute_method:
        return f"// No execute method found for {cls.__name__}\n", dependencies

    # Try to get type hints with forward references resolved
    try:
        cls_module = sys.modules.get(cls.__module__)
        globalns = getattr(cls_module, "__dict__", {}) if cls_module else {}
        localns = {}
        type_hints = typing.get_type_hints(
            execute_method, globalns=globalns, localns=localns
        )
    except Exception:
        type_hints = {}

    sig = inspect.signature(execute_method)
    cls_module = sys.modules.get(cls.__module__)

    use_case_name = cls.__name__

    # Prefer exported domain type aliases (export type X = ...) instead of expanded structural types.
    def _load_domain_alias_structural_ts() -> dict[str, str]:
        out: dict[str, str] = {}
        if DOMAIN_TS_OUT_DIR is None:
            return out
        try:
            for f in DOMAIN_TS_OUT_DIR.glob("*.ts"):
                if f.name == "index.ts":
                    continue
                txt = f.read_text(encoding="utf-8")
                for m in re.finditer(
                    r"^export type\s+(\w+)\s*=\s*(.+)$", txt, flags=re.M
                ):
                    name = m.group(1)
                    rhs = m.group(2).strip().rstrip(";")
                    out[name] = rhs
        except Exception:
            return out
        return out

    domain_alias_ts_definitions: dict[str, str] = _load_domain_alias_structural_ts()

    def _apply_alias_deexpansion(ts_type: str) -> str:
        base = ts_type.strip().rstrip(";")
        nullable = False
        if base.endswith("| null"):
            nullable = True
            base = base[: -len("| null")].strip()

        base_norm = re.sub(r"\s+", " ", base)

        def _strip_partial(s: str) -> str:
            s = s.strip()
            if s.startswith("Partial<") and s.endswith(">"):
                return s[len("Partial<") : -1].strip()
            return s

        # Prefer alias names when the inferred type matches the alias structural definition.
        # When we pick an alias, we also add it as a dependency so the generated TS file imports it.
        for alias_name, rhs in domain_alias_ts_definitions.items():
            rhs_norm = re.sub(r"\s+", " ", rhs.strip().rstrip(";"))

            def _add_alias_dependency() -> None:
                # Best-effort: import from the domain barrel. Use a domain.* module so
                # `generate_typescript_imports` can map it to a .ts file (and thus '@/domain' via the barrel).
                dependencies.add((alias_name, "domain.exchange_rate"))

            if base_norm == rhs_norm:
                _add_alias_dependency()
                return f"{alias_name} | null" if nullable else alias_name

            if (
                _strip_partial(rhs_norm) == base_norm
                or _strip_partial(base_norm) == rhs_norm
            ):
                _add_alias_dependency()
                return f"{alias_name} | null" if nullable else alias_name

        return ts_type

    # Parameters (skip self)
    params = []
    import_aliases: dict[str, str] = {}

    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue

        param_type = type_hints.get(param_name)
        if param_type is None:
            param_type = param.annotation

        if param_type == inspect.Parameter.empty:
            ts_type = "any"
        elif isinstance(param_type, str):
            if cls_module and hasattr(cls_module, param_type):
                resolved_type = getattr(cls_module, param_type)
                ts_type = python_type_to_typescript(resolved_type, module_name)
                dependencies.update(
                    collect_type_dependencies(resolved_type, module_name, set())
                )
            else:
                ts_type = param_type
        else:
            ts_type = python_type_to_typescript(param_type, module_name)
            dependencies.update(
                collect_type_dependencies(param_type, module_name, set())
            )

        # Alias de-expansion for parameters
        ts_type = _apply_alias_deexpansion(ts_type)

        # If a referenced TS type collides with the use case interface name, alias the import.
        if ts_type == use_case_name:
            alias = f"{use_case_name}Request"
            import_aliases[use_case_name] = alias
            ts_type = alias

        camel_param = re.sub(r"_([a-z])", lambda m: m.group(1).upper(), param_name)
        params.append(f"{camel_param}: {ts_type}")

    # Return type
    return_type = type_hints.get("return")
    if return_type is None:
        return_type = sig.return_annotation

    if return_type == inspect.Signature.empty or return_type is None:
        ts_return = "void"
    elif isinstance(return_type, str):
        if cls_module and hasattr(cls_module, return_type):
            resolved_type = getattr(cls_module, return_type)
            ts_return = python_type_to_typescript(resolved_type, module_name)
            dependencies.update(
                collect_type_dependencies(resolved_type, module_name, set())
            )
        else:
            ts_return = return_type
    else:
        ts_return = python_type_to_typescript(return_type, module_name)
        dependencies.update(collect_type_dependencies(return_type, module_name, set()))

    # Alias de-expansion for return
    ts_return = _apply_alias_deexpansion(ts_return)

    # Always async if forced (or coroutine in Python)
    is_async = inspect.iscoroutinefunction(execute_method) or FORCE_ASYNC_USE_CASES
    if is_async:
        ts_return = f"Promise<{ts_return}>"

    params_str = ", ".join(params)

    # Interface with execute method
    lines = [f"export interface {use_case_name} {{"]
    lines.append(f"  execute({params_str}): {ts_return}")
    lines.append("}")

    # Register aliases for this use case (used later by file-level import generation)
    key = f"{module_name}:{use_case_name}"
    if import_aliases:
        USE_CASE_IMPORT_ALIASES[key] = dict(import_aliases)

    return "\n".join(lines), dependencies


def _camelize_identifier(name: str) -> str:
    return re.sub(r"_([a-z])", lambda m: m.group(1).upper(), name)


def python_annotation_str_to_ts(
    type_str: str, module_name: str, defined_in_file: set
) -> str:
    """Convert stringified Python annotations (future annotations) into TS types."""
    s = type_str.strip()

    def _is_record_key_ts(ts_key: str, key_py: object | None = None) -> bool:
        """Return True if key can be emitted as Record<K, V>.

        - primitives are ok
        - Enum subclasses are ok (e.g. BackupFileType)
        """
        k = ts_key.strip()
        if k in {"string", "number", "symbol"}:
            return True
        try:
            from enum import Enum

            if inspect.isclass(key_py) and issubclass(key_py, Enum):
                return True
        except Exception:
            pass
        return False

    def _dict_ts(key_ts: str, val_ts: str, key_py: object | None = None) -> str:
        if _is_record_key_ts(key_ts, key_py=key_py):
            return f"Record<{key_ts}, {val_ts}>"
        return f"Map<{key_ts}, {val_ts}>"

    # Strip quotes if present
    if (s.startswith("'") and s.endswith("'")) or (
        s.startswith('"') and s.endswith('"')
    ):
        s = s[1:-1].strip()

    # Primitive tokens
    if s in {"str", "builtins.str"}:
        return "string"
    if s in {"int", "float", "builtins.int", "builtins.float"}:
        return "number"
    if s in {"bool", "builtins.bool"}:
        return "boolean"
    if s in {"None", "NoneType"}:
        return "null"
    if s in {"Any", "typing.Any"}:
        return "any"
    if s in {"bytes", "builtins.bytes"}:
        return "Uint8Array"
    if s in {"type", "builtins.type"}:
        return "string"

    # Common special classes represented as tokens
    if s in {"UUID", "uuid.UUID"}:
        return "string"
    if s in {"datetime", "date", "datetime.datetime", "datetime.date"}:
        return "string"
    if s in {"Path", "pathlib.Path"}:
        return "string"
    if s == "Dezimal" or s.endswith(".Dezimal"):
        return "Dezimal"

    # Optional[...] (string form)
    if s.startswith("Optional[") and s.endswith("]"):
        inner = s[len("Optional[") : -1]
        return (
            f"{python_annotation_str_to_ts(inner, module_name, defined_in_file)} | null"
        )

    # List[...] / list[...]
    for prefix in ("List[", "list["):
        if s.startswith(prefix) and s.endswith("]"):
            inner = s[len(prefix) : -1]
            return (
                f"{python_annotation_str_to_ts(inner, module_name, defined_in_file)}[]"
            )

    # Dict[K, V] / dict[K, V]
    for prefix in ("Dict[", "dict["):
        if s.startswith(prefix) and s.endswith("]"):
            inner = s[len(prefix) : -1]
            # Split top-level comma
            depth = 0
            parts = []
            buf = []
            for ch in inner:
                if ch == "[":
                    depth += 1
                elif ch == "]":
                    depth -= 1
                elif ch == "," and depth == 0:
                    parts.append("".join(buf).strip())
                    buf = []
                    continue
                buf.append(ch)
            if buf:
                parts.append("".join(buf).strip())
            if len(parts) == 2:
                k_raw = parts[0].strip()
                v_raw = parts[1].strip()

                k_ts = python_annotation_str_to_ts(k_raw, module_name, defined_in_file)
                v_ts = python_annotation_str_to_ts(v_raw, module_name, defined_in_file)

                # Try to resolve the key symbol from the module so we can detect Enums.
                key_py = None
                try:
                    mod = sys.modules.get(module_name)
                    if mod is not None and re.fullmatch(
                        r"[A-Za-z_][A-Za-z0-9_]*", k_raw
                    ):
                        key_py = getattr(mod, k_raw, None)
                except Exception:
                    key_py = None

                return _dict_ts(k_ts, v_ts, key_py=key_py)
            return "Record<string, any>"

    # PEP604 union: A | B | None
    if "|" in s:
        parts = [p.strip() for p in s.split("|")]
        ts_parts = [
            python_annotation_str_to_ts(p, module_name, defined_in_file) for p in parts
        ]
        return " | ".join(ts_parts)

    # If it looks like a forward-ref / domain type name, keep as-is
    # (e.g., SavingsPeriodEntry, SavingsPeriodicity)
    return s


def _camelize_identifier(name: str) -> str:
    return re.sub(r"_([a-z])", lambda m: m.group(1).upper(), name)


if __name__ == "__main__":
    current_path = Path(__file__).parent
    finanze_dir = current_path / "finanze"

    # Preload domain modules to ensure type resolution works for use cases
    domain_dir = finanze_dir / "domain"
    for domain_file in domain_dir.glob("*.py"):
        if domain_file.name != "__init__.py":
            module_name = f"domain.{domain_file.stem}"
            if module_name not in sys.modules:
                try:
                    spec = importlib.util.spec_from_file_location(
                        module_name, domain_file
                    )
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                except Exception:
                    pass

    # Directories to process
    directories_to_process = [
        {
            "source": finanze_dir / "domain",
            "target": current_path / "mobile" / "src" / "domain" / "core",
            "module_prefix": "domain",
            "recursive": False,
        },
        {
            "source": finanze_dir / "domain" / "use_cases",
            "target": current_path / "mobile" / "src" / "domain" / "usecases" / "core",
            "module_prefix": "domain.use_cases",
            "recursive": False,
        },
        {
            "source": finanze_dir / "infrastructure" / "repository",
            "target": current_path
            / "mobile"
            / "src"
            / "services"
            / "database"
            / "repositories"
            / "queries"
            / "core",
            "module_prefix": "infrastructure.repository",
            "recursive": True,
            "include_glob": "**/queries.py",
        },
        {
            "source": finanze_dir / "application" / "ports",
            "target": current_path
            / "mobile"
            / "src"
            / "application"
            / "ports"
            / "core",
            "module_prefix": "application.ports",
            "recursive": False,
            "whitelist": {
                "auto_contributions_port.py",
                "credentials_port.py",
                "crypto_wallet_connection_port.py",
                "entity_port.py",
                "external_entity_port.py",
                "last_fetches_port.py",
                "virtual_import_registry.py",
                "transaction_port.py",
                "position_port.py",
                "pending_flow_port.py",
                "periodic_flow_port.py",
                "real_estate_port.py",
                "backup_processor.py",
                "backup_repository.py",
                "crypto_price_provider.py",
                "exchange_rate_provider.py",
                "exchange_rate_storage.py",
                "metal_price_provider.py",
            },
        },
    ]

    # Set output roots for dynamic TS import generation
    DOMAIN_TS_OUT_DIR = directories_to_process[0]["target"]
    USE_CASE_TS_OUT_DIR = directories_to_process[1]["target"]
    PORTS_TS_OUT_DIR = directories_to_process[-1]["target"]

    # Files to exclude from transpilation
    exclude_patterns = [
        "user_login.py",
        "dezimal.py",
        "template*.py",
        "importing*.py",
        "import_file.py",
        "import_sheets.py",
        "user_logout.py",
        "export*.py",
        "data_init.py",
        "base.py",
    ]

    def should_exclude(filename: str) -> bool:
        """Check if a file should be excluded based on patterns"""
        import fnmatch

        for pattern in exclude_patterns:
            if fnmatch.fnmatch(filename, pattern):
                return True
        return False

    generated_ts_files_by_target: dict[Path, list[Path]] = {}

    for dir_config in directories_to_process:
        domain_dir = dir_config["source"]
        target_base_path = dir_config["target"]
        module_prefix = dir_config["module_prefix"]
        recursive = bool(dir_config.get("recursive", False))
        include_glob = dir_config.get("include_glob")
        whitelist = set(dir_config.get("whitelist", set()))

        # Create target directory if it doesn't exist
        target_base_path.mkdir(parents=True, exist_ok=True)

        generated_ts_files_by_target.setdefault(target_base_path, [])

        print(f"\nProcessing {domain_dir.name}...")

        # Select files
        if include_glob:
            source_files = [
                f
                for f in domain_dir.glob(include_glob)
                if f.is_file()
                and f.name != "__init__.py"
                and not should_exclude(f.name)
                and (not whitelist or f.name in whitelist)
            ]
        else:
            glob_pattern = "**/*.py" if recursive else "*.py"
            source_files = [
                f
                for f in domain_dir.glob(glob_pattern)
                if f.is_file()
                and f.name != "__init__.py"
                and not should_exclude(f.name)
                and (not whitelist or f.name in whitelist)
            ]

        domain_files = sorted(source_files)

        for domain_file in domain_files:
            # Convert snake_case filename to camelCase
            file_stem = domain_file.stem
            camel_case_name = re.sub(
                r"_([a-z])", lambda m: m.group(1).upper(), file_stem
            )

            # If we're processing recursively and multiple files share the same stem
            # (like many 'queries.py'), make the output name include the relative path.
            unique_suffix = ""
            if recursive:
                try:
                    # Prefer to namespace by the first directory under the root.
                    rel_parent = domain_file.parent.relative_to(domain_dir)
                    rel_parts = [p for p in rel_parent.parts if p and p != "."]
                    if rel_parts:
                        unique_suffix = _camelize_identifier(rel_parts[0])
                except Exception:
                    unique_suffix = ""

            out_name = camel_case_name
            if unique_suffix:
                out_name = (
                    f"{unique_suffix}{camel_case_name[0].upper()}{camel_case_name[1:]}"
                )

            target_file = target_base_path / f"{out_name}.ts"

            # Get the set of classes actually defined in this file
            defined_classes = get_defined_classes(domain_file)

            # Get type aliases defined in this file
            type_aliases_names = get_type_aliases(domain_file)

            # Dynamically import the module with new domain.xxx format
            module_name = f"{module_prefix}.{file_stem}"
            spec = importlib.util.spec_from_file_location(module_name, domain_file)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module

            try:
                spec.loader.exec_module(module)
            except Exception as e:
                print(f"✗ Error loading module {module_name}: {e}")
                continue

            # For use case files, check if they depend on excluded domain files
            is_use_case_dir = "use_cases" in str(domain_file)
            if is_use_case_dir:
                # Read the file to check imports
                with open(domain_file, "r") as f:
                    file_content = f.read()

                # Check if it imports from any excluded domain files
                skip_use_case = False
                for pattern in exclude_patterns:
                    # Convert pattern to module name (e.g., "template*.py" -> "template")
                    module_pattern = pattern.replace("*.py", "").replace(".py", "")
                    if (
                        f"from domain.{module_pattern}" in file_content
                        or f"import domain.{module_pattern}" in file_content
                    ):
                        print(
                            f"⊘ Skipping {file_stem}.py (depends on excluded {module_pattern})"
                        )
                        skip_use_case = True
                        break

                if skip_use_case:
                    continue

            # Unified declarations in order
            decls_in_order = get_declarations_in_order(domain_file)

            # Compute defined names set for same-file import suppression
            all_defined_names = {name for _, name in decls_in_order}

            types_to_convert = []
            for kind, name in decls_in_order:
                obj = getattr(module, name, None)
                if obj is None:
                    continue

                if kind == "class":
                    if inspect.isclass(obj):
                        types_to_convert.append(obj)
                else:
                    # alias
                    import types as _types

                    is_supported_alias = hasattr(obj, "__origin__") or isinstance(
                        obj, _types.UnionType
                    )
                    if is_supported_alias:

                        class TypeAliasWrapper:
                            def __init__(self, type_hint, name, module):
                                self._type_hint = type_hint
                                self.__name__ = name
                                self.__module__ = module.__name__
                                if hasattr(type_hint, "__origin__"):
                                    self.__origin__ = type_hint.__origin__
                                if hasattr(type_hint, "__args__"):
                                    self.__args__ = type_hint.__args__

                        types_to_convert.append(TypeAliasWrapper(obj, name, module))

            # Only generate if there are types to convert
            if types_to_convert:
                print(
                    f"Generating {target_file.name} with {len(types_to_convert)} types from {domain_file.name}..."
                )

                # Check if these are use case classes (abstract classes with execute method)
                import abc

                are_use_cases = all(
                    hasattr(cls, "execute") and isinstance(cls, abc.ABCMeta)
                    for cls in types_to_convert
                )

                # Generate TypeScript manually
                if are_use_cases:
                    print("  Generating use case types...")
                else:
                    print("  Generating TypeScript interfaces...")

                try:
                    # Collect all dependencies and generate interfaces
                    all_dependencies = set()
                    interface_codes = []

                    for cls in types_to_convert:
                        interface_code, deps = generate_typescript_interface(
                            cls, module_name, all_defined_names
                        )
                        interface_codes.append(interface_code)
                        all_dependencies.update(deps)

                    # Collect import aliases from generated use cases (for name collision resolution)
                    import_aliases = {}
                    if are_use_cases:
                        for cls in types_to_convert:
                            key = f"{module_name}:{cls.__name__}"
                            m = USE_CASE_IMPORT_ALIASES.get(key)
                            if isinstance(m, dict):
                                import_aliases.update(m)

                    # Generate the full file content with imports at the top
                    lines = []

                    # Add imports if there are dependencies
                    imports_str = generate_typescript_imports(
                        all_dependencies,
                        is_use_case=are_use_cases,
                        import_aliases=import_aliases,
                        from_dir=target_base_path,
                    )
                    # Only apply import dead-code elimination for ports/use cases.
                    # For domain core files, dependency collection is the single source of truth and
                    # filtering can accidentally remove required imports like Dezimal.
                    if imports_str and target_base_path in {
                        PORTS_TS_OUT_DIR,
                        USE_CASE_TS_OUT_DIR,
                    }:
                        # Filter unused imports based on the actually emitted TS declarations.
                        emitted_body = "\n\n".join(interface_codes)
                        filtered_import_lines: list[str] = []
                        for imp_line in imports_str.splitlines():
                            m = re.match(
                                r"^import\s+\{\s*([^}]*)\s*}\s+from\s+(['\"])([^'\"]+)\2;\s*$",
                                imp_line,
                            )
                            if not m:
                                filtered_import_lines.append(imp_line)
                                continue

                            names_blob = m.group(1)
                            spec = m.group(3)

                            names_raw = [
                                p.strip() for p in names_blob.split(",") if p.strip()
                            ]
                            used_names: list[str] = []
                            for part in names_raw:
                                # support `Foo as Bar`
                                local_name = part.split(" as ")[-1].strip()
                                if re.search(
                                    rf"\b{re.escape(local_name)}\b", emitted_body
                                ):
                                    used_names.append(part)

                            if used_names:
                                filtered_import_lines.append(
                                    f"import {{ {', '.join(used_names)} }} from '{spec}';"
                                )

                        imports_str = "\n".join(filtered_import_lines).strip()

                    if imports_str:
                        lines.append(imports_str)
                        lines.append("")

                    # Add all interfaces
                    for interface_code in interface_codes:
                        lines.append(interface_code)
                        lines.append("")

                    with open(target_file, "w") as f:
                        f.write("\n".join(lines))

                    generated_ts_files_by_target[target_base_path].append(target_file)

                    print(f"✓ Generated {target_file}")
                except Exception as e:
                    print(f"✗ Error generating interfaces for {target_file.name}: {e}")
                    import traceback

                    traceback.print_exc()

    # Generate barrel index.ts files
    def write_index_ts(target_dir: Path, files: list[Path]) -> None:
        # Export all .ts files except index.ts itself
        module_names = []
        for p in files:
            if p.suffix != ".ts":
                continue
            if p.name == "index.ts":
                continue
            module_names.append(p.stem)

        module_names = sorted(set(module_names))

        lines = [f'export * from "./{name}"' for name in module_names]
        index_path = target_dir / "index.ts"
        index_path.write_text("\n".join(lines) + ("\n" if lines else ""))

    for target_dir, files in generated_ts_files_by_target.items():
        if files:
            write_index_ts(target_dir, files)

    # Run prettier on generated TypeScript files
    print("\nFormatting generated TypeScript files with prettier...")
    mobile_dir = current_path / "mobile"
    try:
        import subprocess

        # Format all generated target directories (relative to mobile)
        for target_dir, files in generated_ts_files_by_target.items():
            if not files:
                continue
            try:
                rel = target_dir.relative_to(mobile_dir)
            except Exception:
                continue

            result = subprocess.run(
                ["pnpm", "exec", "prettier", rel.as_posix(), "--write"],
                cwd=mobile_dir,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                print(f"✓ Formatted {rel.as_posix()}")
            else:
                print(
                    f"⚠ Prettier formatting had issues for {rel.as_posix()}: {result.stderr}"
                )
    except Exception as e:
        print(f"⚠ Could not run prettier: {e}")
