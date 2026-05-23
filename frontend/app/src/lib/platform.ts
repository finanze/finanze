import { PlatformInfo, PlatformType } from "@/types"

export function getPlatformInfo(): PlatformInfo {
  return window.platform ?? { type: PlatformType.WEB }
}

export function getPlatformType(): PlatformType {
  return getPlatformInfo().type
}

export function isNativeMobile(): boolean {
  const type = getPlatformType()
  return type === PlatformType.IOS || type === PlatformType.ANDROID
}

export function isElectron(): boolean {
  return typeof window !== "undefined" && typeof window.ipcAPI !== "undefined"
}

export function isWeb(): boolean {
  return !isElectron() && !isNativeMobile()
}

export function isIOS(): boolean {
  return getPlatformType() === PlatformType.IOS
}

export function isAndroid(): boolean {
  return getPlatformType() === PlatformType.ANDROID
}

export function hasNativeFileSystem(): boolean {
  return isElectron()
}

export function hasLocalBackend(): boolean {
  return isElectron() || !isNativeMobile()
}

export function usesPyodide(): boolean {
  return isNativeMobile()
}

export function isPWAStandalone(): boolean {
  if (typeof window === "undefined") return false
  if ((navigator as { standalone?: boolean }).standalone) return true
  return window.matchMedia("(display-mode: standalone)").matches
}
