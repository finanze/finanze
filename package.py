import argparse
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("packager")

cwd = Path.cwd()
dist_directory = cwd / "dist"
backend_dir = cwd / "backend" / "dist"


def move_to_dist(file: Path):
    dist_directory.mkdir(exist_ok=True)
    shutil.move(src=file, dst=dist_directory)


# --- Argument Parsing ---
parser = argparse.ArgumentParser(
    description="Package frontend, backend, or full application."
)
parser.add_argument(
    "--target",
    choices=["backend", "frontend", "full"],
    default="full",
    help='Specify what to package: "backend", "frontend", or "full" (default: "full")',
)
parser.add_argument(
    "--os",
    choices=["mac", "win", "linux"],
    default=None,
    help='Specify target OS: "mac", "win", or "linux" (default: None for all platforms)',
)
parser.add_argument(
    "--arch",
    choices=["x64", "arm64"],
    default=None,
    help='Specify target architecture: "x64" or "arm64" (default: None, only applies to macOS)',
)
args = parser.parse_args()

# --- Backend Packaging ---
if args.target in ["backend", "full"]:
    logger.info("Starting backend packaging...")
    package_server = subprocess.call(
        f"pyinstaller --clean --distpath {backend_dir} finanze.spec", shell=True
    )
    if package_server != 0:
        logger.error("Backend packaging failed")
        sys.exit(1)

    logger.info("Backend packaging successful.")

# --- Frontend Packaging ---
if args.target in ["frontend", "full"]:
    logger.info("Starting frontend packaging...")
    front_dir = cwd / "frontend" / "app"

    env = os.environ.copy()

    os.chdir(front_dir)
    pinstall_front = subprocess.call("pnpm install", shell=True, env=env)
    if pinstall_front != 0:
        logger.error("Frontend installation failed")
        sys.exit(1)

    # Build pnpm dist command with OS and arch parameters
    pnpm_dist_cmd = "pnpm run dist"
    if args.os:
        pnpm_dist_cmd += f":{args.os}"
        if args.arch and args.os == "mac":
            pnpm_dist_cmd += f":{args.arch}"

    logger.info(f"Running: {pnpm_dist_cmd}")
    if "VITE_SUPABASE_URL" in env:
        logger.info("VITE_SUPABASE_URL is set")
    if "VITE_SUPABASE_PUBLISHABLE_KEY" in env:
        logger.info("VITE_SUPABASE_PUBLISHABLE_KEY is set")

    package_front = subprocess.call(pnpm_dist_cmd, shell=True, env=env)
    if package_front != 0:
        logger.error("Frontend packaging failed")
        sys.exit(1)

    logger.info("Frontend packaging successful.")

    logger.info("Moving frontend release files to dist directory...")
    front_release_dir = front_dir / "release"
    # Ensure dist_directory exists before moving files into it
    dist_directory.mkdir(exist_ok=True)
    for path in front_release_dir.iterdir():
        name = path.name
        if path.is_dir() or name in {
            "builder-debug.yml",
            "builder-effective-config.yaml",
        }:
            continue

        file_ext = ["dmg", "zip", "exe", "AppImage", "tar.xz", "deb", "blockmap"]
        if any(name.endswith(ext) for ext in file_ext) or (
            name.startswith("latest") and name.endswith(".yml")
        ):
            # Rename latest-arm64-mac.yml to latest-mac.yml for macOS ARM64
            if (
                args.os == "mac"
                and args.arch == "arm64"
                and name == "latest-arm64-mac.yml"
            ):
                renamed_path = path.parent / "latest-mac.yml"
                path.rename(renamed_path)
                logger.info(f"Renamed {name} to latest-mac.yml")
                move_to_dist(renamed_path)
            else:
                move_to_dist(path)

    logger.info("Frontend release files moved.")

logger.info("Completed.")
