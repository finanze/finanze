import argparse
import ast
import json
import os
import re
import subprocess
import tomllib
from pathlib import Path

REGISTRY = "finanze/infrastructure/repository/db/version_registry.py"
STABLE = re.compile(r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")
METADATA_FILE = Path("frontend/app/finanze-build.json")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def source(path: str, ref: str | None) -> str:
    return git("show", f"{ref}:{path}") if ref else Path(path).read_text()


def migrations(ref: str | None = None) -> list[str]:
    registry = ast.parse(source(REGISTRY, ref))
    imports = {
        alias.asname or alias.name: (node.module, alias.name)
        for node in registry.body
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    entries = next(
        node.value
        for node in registry.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "versions" for t in node.targets)
    )
    if not isinstance(entries, ast.List):
        raise ValueError("The migration registry must be a list of migration instances")
    names = []
    for entry in entries.elts:
        if not isinstance(entry, ast.Call) or not isinstance(entry.func, ast.Name):
            raise ValueError("Expected an imported migration class in the registry")
        module, symbol = imports[entry.func.id]
        if not module:
            raise ValueError(f"{symbol} must be imported from its migration module")
        tree = ast.parse(source(f"finanze/{module.replace('.', '/')}.py", ref))
        migration = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == symbol
        )
        name = next(
            node
            for node in migration.body
            if isinstance(node, ast.FunctionDef) and node.name == "name"
        )
        value = next(node.value for node in name.body if isinstance(node, ast.Return))
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            raise ValueError(f"{symbol}.name must return a permanent string literal")
        names.append(value.value)
    if not names or len(set(names)) != len(names):
        raise ValueError("Migration registry is empty or contains duplicate names")
    return names


def stable_tags(*args: str) -> list[str]:
    return [
        tag
        for tag in git("tag", "--list", "--sort=-version:refname", *args).splitlines()
        if STABLE.fullmatch(tag)
    ]


def published_migrations() -> tuple[list[str], list[str]]:
    stable = stable_tags()
    return (
        migrations(stable[0]) if stable else [],
        migrations("next") if git("tag", "--list", "next") else [],
    )


def validate_history(
    channel: str, current: list[str], stable: list[str], next_build: list[str]
) -> None:
    stable_names = set(stable)
    if channel == "stable":
        if [name for name in current if name in stable_names] != stable:
            raise ValueError("Build must preserve the published stable migration order")
        return
    if not stable_names.issubset(current):
        raise ValueError("Build must preserve the published stable migration history")
    next_names = set(next_build)
    if [name for name in current if name in next_names] != next_build:
        raise ValueError("Build diverges from the published next migration history")


def build_preview(pr: int | None) -> None:
    tags = stable_tags("--merged", "HEAD")
    if not tags:
        raise ValueError("No stable release tag is reachable from this build")
    tag = tags[0]
    base = tag[1:]
    sha = git("rev-parse", "HEAD")
    if pr is not None:
        channel = "pr"
        label = f"pr{pr}-{base}-{sha[:8]}"
        package_version = f"{base}-pr.{pr}.g{sha[:8]}"
    else:
        channel = "next"
        count = int(git("rev-list", "--count", f"{tag}..HEAD"))
        label = f"next-{base}-dev{count}-{sha[:8]}"
        package_version = f"{base}-next.{count}"
    current = migrations()
    if pr is None:
        validate_history("next", current, *published_migrations())
    data = {
        "version": label,
        "channel": channel,
        "base_version": base,
        "commit": sha,
        "package_version": package_version,
    }
    print(f"version={label}")
    print(f"metadata={json.dumps(data, separators=(',', ':'))}")


def apply_preview(electron: bool) -> None:
    data = json.loads(os.environ["BUILD_METADATA"])
    if data["commit"] != git("rev-parse", "HEAD"):
        raise ValueError("Build metadata does not match the checked-out commit")
    METADATA_FILE.write_text(json.dumps(data))
    version_file = Path("finanze/version.py")
    version_file.write_text(f"__version__ = {json.dumps(data['version'])}\n")
    if electron:
        package_path = Path("frontend/app/package.json")
        package = json.loads(package_path.read_text())
        package["version"] = data["package_version"]
        package_path.write_text(json.dumps(package, indent=2) + "\n")
        builder_path = Path("frontend/app/electron-builder.json")
        builder = json.loads(builder_path.read_text())
        builder["artifactName"] = builder["artifactName"].replace(
            "${version}", data["version"]
        )
        builder_path.write_text(json.dumps(builder, indent=2) + "\n")


def verify_stable(tag: str) -> None:
    if not STABLE.fullmatch(tag):
        raise ValueError(f"Invalid stable release tag: {tag}")
    config = tomllib.loads(Path(".bumpversion.toml").read_text())
    if config["tool"]["bumpversion"]["current_version"] != tag[1:]:
        raise ValueError("Release tag does not match the checked-out version")
    if tag in stable_tags() and git("rev-parse", f"{tag}^{{commit}}") != git(
        "rev-parse", "HEAD"
    ):
        raise ValueError(f"{tag} already points to a different commit")
    current = migrations()
    stable, next_build = published_migrations()
    validate_history("stable", current, stable, next_build)


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    preview = commands.add_parser("preview")
    preview.add_argument("--pr", type=int)
    apply = commands.add_parser("apply")
    apply.add_argument("--electron", action="store_true")
    stable = commands.add_parser("stable")
    stable.add_argument("tag")
    commands.add_parser("verify-next")
    args = parser.parse_args()
    match args.command:
        case "preview":
            build_preview(args.pr)
        case "apply":
            apply_preview(args.electron)
        case "stable":
            verify_stable(args.tag)
        case "verify-next":
            validate_history("next", migrations(), *published_migrations())


if __name__ == "__main__":
    main()
