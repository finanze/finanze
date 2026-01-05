import {
  PlatformType,
  type PlatformInfo as RendererPlatformInfo,
} from "../../src/types"
import { OS, type PlatformInfo as ElectronPlatformInfo } from "../types"

function getOSFromNodePlatform(platform: NodeJS.Platform): OS {
  switch (platform) {
    case "darwin":
      return OS.MAC
    case "win32":
      return OS.WINDOWS
    default:
      return OS.LINUX
  }
}

function getPlatformTypeFromOS(os: OS): PlatformType {
  switch (os) {
    case OS.MAC:
      return PlatformType.MAC
    case OS.WINDOWS:
      return PlatformType.WINDOWS
    case OS.LINUX:
      return PlatformType.LINUX
  }
}

function getSystemVersion(): string | undefined {
  const fn: unknown = (process as any).getSystemVersion
  return typeof fn === "function" ? (fn as () => string)() : undefined
}

export function getElectronOS(): OS {
  return getOSFromNodePlatform(process.platform)
}

export function getRendererPlatformInfo(): RendererPlatformInfo {
  const os = getElectronOS()

  return {
    type: getPlatformTypeFromOS(os),
    arch: process.arch,
    osVersion: getSystemVersion(),
    electronVersion: process.versions.electron,
    chromiumVersion: process.versions.chrome,
    nodeVersion: process.versions.node,
  }
}

export function getElectronPlatformInfo(): ElectronPlatformInfo {
  const os = getElectronOS()

  return {
    type: os,
    arch: process.arch,
    osVersion: getSystemVersion(),
    electronVersion: process.versions.electron,
  }
}
