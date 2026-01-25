import { isNativeMobile } from "@/lib/platform"

export async function preinit(): Promise<void> {
  if (!__MOBILE__) return

  const { initializeCapacitorPlatform } = await import("@/lib/capacitor")
  await initializeCapacitorPlatform()
}

export function init() {
  if (!__MOBILE__) return
  if (!isNativeMobile()) return

  import("@/lib/pyodide/init").then(({ ensureCoreInitialized }) => {
    ensureCoreInitialized()
  })
}

export function triggerDeferredInit() {
  if (!__MOBILE__) return
  if (!isNativeMobile()) return

  import("@/lib/pyodide/init").then(({ triggerDeferredInit }) => {
    triggerDeferredInit()
  })
}

export function hideSplashScreen() {
  if (!__MOBILE__) return
  if (!isNativeMobile()) return

  import("@/lib/capacitor/init").then(({ hideSplashScreen }) => {
    hideSplashScreen()
  })
}
