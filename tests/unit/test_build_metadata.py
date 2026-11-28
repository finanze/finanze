import json
import os
import runpy
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / ".github/scripts/build_metadata.py"


def test_stable_hotfix_and_next_can_publish_different_migrations(tmp_path):
    def git(*args):
        return subprocess.check_output(
            [
                "git",
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.com",
                "-c",
                "commit.gpgsign=false",
                *args,
            ],
            cwd=tmp_path,
            text=True,
        ).strip()

    def metadata(*args, check=True, **kwargs):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=tmp_path,
            check=check,
            capture_output=True,
            text=True,
            **kwargs,
        )

    git("init")
    root = tmp_path / "finanze/infrastructure/repository/db"
    root.mkdir(parents=True)
    (root / "changes.py").write_text(
        'class Genesis:\n    def name(self):\n        return "v0 Genesis"\n'
        'class Feature:\n    def name(self):\n        return "add_accounts"\n'
        'class Fork:\n    def name(self):\n        return "add_something_else"\n'
    )
    (tmp_path / ".bumpversion.toml").write_text(
        '[tool.bumpversion]\ncurrent_version = "0.11.1"\n'
    )

    def commit_registry(*names):
        (root / "version_registry.py").write_text(
            "from infrastructure.repository.db.changes import Genesis, Feature, Fork\n"
            f"versions = [{', '.join(name + '()' for name in names)}]\n"
        )
        git("add", ".")
        git("commit", "-m", "Register " + ", ".join(names))
        return git("rev-parse", "HEAD")

    commit_registry("Genesis")
    git("tag", "v0.11.0")
    commit_registry("Genesis", "Feature")
    git("tag", "next")
    sha = commit_registry("Genesis", "Feature", "Fork")

    version, manifest = metadata("preview").stdout.splitlines()
    assert version == f"version=next-0.11.0-dev2-{sha[:8]}"
    parsed_next = json.loads(manifest.removeprefix("metadata="))
    assert parsed_next["package_version"] == "0.11.0-next.2"

    git("checkout", "--detach", "v0.11.0")
    sha = commit_registry("Genesis", "Fork")
    assert metadata("stable", "v0.11.1").stdout.strip() == ""
    version, manifest = metadata("preview", "--pr", "342").stdout.splitlines()
    assert version == f"version=pr342-0.11.0-{sha[:8]}"
    manifest = manifest.removeprefix("metadata=")
    rejected = metadata("verify-next", check=False)
    assert rejected.returncode != 0
    assert "diverges from the published next migration history" in rejected.stderr

    frontend = tmp_path / "frontend/app"
    frontend.mkdir(parents=True)
    (frontend / "package.json").write_text('{"version":"0.11.0"}')
    (frontend / "electron-builder.json").write_text(
        '{"artifactName":"Finanze-${version}-${os}.${ext}"}'
    )
    metadata("apply", "--electron", env=os.environ | {"BUILD_METADATA": manifest})
    packaged = runpy.run_path(str(tmp_path / "finanze/version.py"))
    assert packaged["__version__"] == f"pr342-0.11.0-{sha[:8]}"
    assert json.loads((frontend / "package.json").read_text())["version"] == (
        f"0.11.0-pr.342.g{sha[:8]}"
    )
    assert (
        json.loads((frontend / "electron-builder.json").read_text())["artifactName"]
        == f"Finanze-pr342-0.11.0-{sha[:8]}-${{os}}.${{ext}}"
    )
    assert json.loads((frontend / "finanze-build.json").read_text()) == json.loads(
        manifest
    )

    git("tag", "v0.11.1")
    git("checkout", "--detach", "next")
    rejected = metadata("verify-next", check=False)
    assert rejected.returncode != 0
    assert "preserve the published stable migration history" in rejected.stderr

    (tmp_path / ".bumpversion.toml").write_text(
        '[tool.bumpversion]\ncurrent_version = "0.12.0"\n'
    )
    commit_registry("Genesis", "Feature", "Fork")
    metadata("verify-next")
    assert metadata("stable", "v0.12.0").stdout.strip() == ""
