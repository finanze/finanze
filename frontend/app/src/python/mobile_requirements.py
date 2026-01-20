import sys
import traceback


async def install() -> None:
    print("Installing mobile requirements...")
    print(f"Python: {sys.version}")
    print(f"Platform: {sys.platform}")
    print("Installing from local Pyodide packages + local wheels (offline)...")

    try:
        try:
            import micropip
        except ImportError as e:
            raise RuntimeError(
                f"micropip import failed: {e!r}. Ensure runtime loads it via pyodide.loadPackage('micropip') and that /pyodide contains the matching wheel assets."
            ) from e

        try:
            from wheels_manifest import LOCAL_WHEELS, PYODIDE_PACKAGES
        except ImportError as e:
            raise RuntimeError(
                f"Missing wheels_manifest (import error: {e!r}). Ensure build:python ran so /python/wheels_manifest.py exists and /python is served from dist/python."
            ) from e

        await micropip.install(PYODIDE_PACKAGES, keep_going=False)
        await micropip.install(LOCAL_WHEELS, deps=False, keep_going=False)
    except Exception:
        traceback.print_exc()
        raise
