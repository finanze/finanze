import { Capacitor } from "@capacitor/core"
import { SafeArea } from "capacitor-plugin-safe-area"

export type SafeAreaInsets = {
  top: number
  right: number
  bottom: number
  left: number
}

let listenerAttached = false

function setInsetVar(key: keyof SafeAreaInsets, value: number) {
  if (typeof document === "undefined") return
  document.documentElement.style.setProperty(
    `--safe-area-inset-${key}`,
    `${value}px`,
  )
}

export async function getNativeSafeAreaInsets(): Promise<SafeAreaInsets> {
  if (!Capacitor.isNativePlatform()) {
    return { top: 0, right: 0, bottom: 0, left: 0 }
  }

  try {
    const { insets } = await SafeArea.getSafeAreaInsets()
    return {
      top: insets.top ?? 0,
      right: insets.right ?? 0,
      bottom: insets.bottom ?? 0,
      left: insets.left ?? 0,
    }
  } catch {
    return { top: 0, right: 0, bottom: 0, left: 0 }
  }
}

export async function applyNativeSafeAreaCssVars(): Promise<void> {
  if (!Capacitor.isNativePlatform()) return

  const insets = await getNativeSafeAreaInsets()
  for (const [key, value] of Object.entries(insets) as Array<
    [keyof SafeAreaInsets, number]
  >) {
    setInsetVar(key, value)
  }

  if (listenerAttached) return
  listenerAttached = true

  await SafeArea.addListener(
    "safeAreaChanged",
    (data: { insets: SafeAreaInsets }) => {
      const next = data.insets
      setInsetVar("top", next.top ?? 0)
      setInsetVar("right", next.right ?? 0)
      setInsetVar("bottom", next.bottom ?? 0)
      setInsetVar("left", next.left ?? 0)
    },
  )
}

export async function removeNativeSafeAreaListeners(): Promise<void> {
  if (!Capacitor.isNativePlatform()) return
  listenerAttached = false
  await SafeArea.removeAllListeners()
}
