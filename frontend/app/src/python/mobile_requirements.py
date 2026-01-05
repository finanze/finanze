import sys
import traceback


def has_core_packages() -> bool:
    from wheels_manifest import LOCAL_WHEELS_CORE, PYODIDE_PACKAGES_CORE

    return bool(LOCAL_WHEELS_CORE or PYODIDE_PACKAGES_CORE)


async def _ensure_micropip():
    import micropip

    return micropip


async def install() -> None:
    print(f"Python: {sys.version}")
    print(f"Platform: {sys.platform}")

    try:
        from wheels_manifest import LOCAL_WHEELS_CORE, PYODIDE_PACKAGES_CORE
    except ImportError as e:
        raise RuntimeError(
            f"Missing wheels_manifest (import error: {e!r}). Ensure build:python ran so /python/wheels_manifest.py exists and /python is served from dist/python."
        ) from e

    if not LOCAL_WHEELS_CORE and not PYODIDE_PACKAGES_CORE:
        print("No core packages to install, skipping micropip.")
        return

    print("Installing CORE packages from local Pyodide + local wheels (offline)...")
    try:
        micropip = await _ensure_micropip()
        await micropip.install(PYODIDE_PACKAGES_CORE, keep_going=False)
        await micropip.install(LOCAL_WHEELS_CORE, deps=False, keep_going=False)
        print("Core packages installed.")
    except Exception:
        traceback.print_exc()
        raise


async def install_deferred() -> None:
    print("Installing deferred mobile requirements...")
    print("Installing DEFERRED packages from local Pyodide + local wheels (offline)...")

    try:
        from wheels_manifest import LOCAL_WHEELS_DEFERRED, PYODIDE_PACKAGES_DEFERRED

        micropip = await _ensure_micropip()
        await micropip.install(PYODIDE_PACKAGES_DEFERRED, keep_going=False)
        await micropip.install(LOCAL_WHEELS_DEFERRED, deps=False, keep_going=False)
        print("Deferred packages installed.")
    except Exception:
        traceback.print_exc()
        raise
