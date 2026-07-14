import type { PluginListenerHandle } from "@capacitor/core"

export interface ApkDownloadProgress {
  downloaded: number
  total: number
}

interface ApkUpdaterPlugin {
  canInstall(): Promise<{ granted: boolean }>
  openInstallSettings(): Promise<void>
  download(options: {
    url: string
    fileName: string
    expectedSize?: number
    timeout?: number
  }): Promise<{ path: string; size: number }>
  install(options: { path: string }): Promise<void>
  addListener(
    eventName: "downloadProgress",
    listenerFunc: (progress: ApkDownloadProgress) => void,
  ): Promise<PluginListenerHandle>
}

let cachedApkUpdater: ApkUpdaterPlugin | null | undefined

async function getApkUpdater(): Promise<ApkUpdaterPlugin | null> {
  if (!__MOBILE__ || !__CONNECTIONS__) return null
  if (cachedApkUpdater !== undefined) return cachedApkUpdater

  try {
    const { registerPlugin } = await import("@capacitor/core")
    const plugin = registerPlugin<ApkUpdaterPlugin>("ApkUpdater")
    // IMPORTANT: Capacitor plugin proxies are thenable; returning one from an
    // async function makes the runtime await it and call `.then()` on the
    // native proxy (rejects with "not implemented"). Wrap in a plain object.
    cachedApkUpdater = {
      canInstall: () => plugin.canInstall(),
      openInstallSettings: () => plugin.openInstallSettings(),
      download: options => plugin.download(options),
      install: options => plugin.install(options),
      addListener: (eventName, listenerFunc) =>
        plugin.addListener(eventName, listenerFunc),
    }
    return cachedApkUpdater
  } catch {
    cachedApkUpdater = null
    return null
  }
}

export async function apkCanInstall(): Promise<boolean> {
  const plugin = await getApkUpdater()
  if (!plugin) return false
  const { granted } = await plugin.canInstall()
  return granted
}

export async function apkOpenInstallSettings(): Promise<void> {
  const plugin = await getApkUpdater()
  await plugin?.openInstallSettings()
}

export async function apkDownload(
  url: string,
  fileName: string,
  expectedSize?: number,
): Promise<{ path: string; size: number } | null> {
  const plugin = await getApkUpdater()
  if (!plugin) return null
  return plugin.download({ url, fileName, expectedSize })
}

export async function apkInstall(path: string): Promise<void> {
  const plugin = await getApkUpdater()
  await plugin?.install({ path })
}

export async function apkAddProgressListener(
  listenerFunc: (progress: ApkDownloadProgress) => void,
): Promise<PluginListenerHandle | null> {
  const plugin = await getApkUpdater()
  if (!plugin) return null
  return plugin.addListener("downloadProgress", listenerFunc)
}
