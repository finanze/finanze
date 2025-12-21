import type { FeatureFlags } from "@/types"

type Listener = (value: FeatureFlags) => void

let current: FeatureFlags = {}
const listeners = new Set<Listener>()

export const getFeatureFlags = (): FeatureFlags => current

export const setFeatureFlags = (value: FeatureFlags): void => {
  current = value || {}
  for (const listener of listeners) {
    listener(current)
  }
}

export const subscribeFeatureFlags = (listener: Listener): (() => void) => {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}
