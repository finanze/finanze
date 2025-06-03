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

    os.chdir(backend_dir)
    for path in backend_dir.iterdir():
        if path.is_file() and path.name.startswith("finanze-server"):
            new_name = "server"
            path.rename(new_name)
            logger.info(f"Renamed {path.name} to {new_name}")
            break

    logger.info("Backend packaging successful.")

# --- Frontend Packaging ---
if args.target in ["frontend", "full"]:
    logger.info("Starting frontend packaging...")
    front_dir = cwd / "frontend" / "app"

    os.chdir(front_dir)
    pinstall_front = subprocess.call("pnpm install", shell=True)
    if pinstall_front != 0:
        logger.error("Frontend installation failed")
        sys.exit(1)

    package_front = subprocess.call("pnpm run dist", shell=True)
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

        file_ext = ["dmg", "zip", "exe", "AppImage", "tar.xz", "deb"]
        if any(name.endswith(ext) for ext in file_ext):
            move_to_dist(path)

    logger.info("Frontend release files moved.")

logger.info("Completed.")
