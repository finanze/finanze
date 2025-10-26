import { useSyncExternalStore } from "react"
import type {
  ManualPositionAsset,
  ManualPositionDraft,
} from "./manualPositionTypes"

const registry = new Map<ManualPositionAsset, ManualPositionDraft<any>[]>()
const emptyCache = new Map<ManualPositionAsset, ManualPositionDraft<any>[]>()
const deletedRegistry = new Map<ManualPositionAsset, Set<string>>()
const emptyDeletedCache = new Map<ManualPositionAsset, Set<string>>()
const listeners = new Set<() => void>()

const notify = () => {
  listeners.forEach(listener => listener())
}

export function setManualDraftsForAsset(
  asset: ManualPositionAsset,
  drafts: ManualPositionDraft<any>[],
) {
  const current = registry.get(asset)
  if (current === drafts) {
    return
  }
  registry.set(asset, drafts)
  if (emptyCache.has(asset)) {
    emptyCache.delete(asset)
  }
  // Whenever drafts are updated without explicit metadata, ensure deleted ids cache is initialized
  if (!deletedRegistry.has(asset) && !emptyDeletedCache.has(asset)) {
    emptyDeletedCache.set(asset, new Set())
  }
  notify()
}

export function clearManualDraftsForAsset(asset: ManualPositionAsset) {
  registry.delete(asset)
  if (!emptyCache.has(asset)) {
    emptyCache.set(asset, [])
  }
  deletedRegistry.delete(asset)
  if (!emptyDeletedCache.has(asset)) {
    emptyDeletedCache.set(asset, new Set())
  }
  notify()
}

export function getManualDraftsForAsset<Entry extends Record<string, any>>(
  asset: ManualPositionAsset,
): ManualPositionDraft<Entry>[] {
  const stored = registry.get(asset) as ManualPositionDraft<Entry>[] | undefined
  if (stored) {
    return stored
  }
  if (!emptyCache.has(asset)) {
    emptyCache.set(asset, [])
  }
  return emptyCache.get(asset) as ManualPositionDraft<Entry>[]
}

export function useManualDrafts<Entry extends Record<string, any>>(
  asset: ManualPositionAsset,
): ManualPositionDraft<Entry>[] {
  return useSyncExternalStore(
    listener => {
      listeners.add(listener)
      return () => {
        listeners.delete(listener)
      }
    },
    () => {
      const stored = registry.get(asset) as
        | ManualPositionDraft<Entry>[]
        | undefined
      if (stored) return stored
      if (!emptyCache.has(asset)) {
        emptyCache.set(asset, [])
      }
      return emptyCache.get(asset) as ManualPositionDraft<Entry>[]
    },
    () => {
      const stored = registry.get(asset) as
        | ManualPositionDraft<Entry>[]
        | undefined
      if (stored) return stored
      if (!emptyCache.has(asset)) {
        emptyCache.set(asset, [])
      }
      return emptyCache.get(asset) as ManualPositionDraft<Entry>[]
    },
  )
}

export function setManualDeletedOriginalIdsForAsset(
  asset: ManualPositionAsset,
  deletedOriginalIds: Set<string>,
) {
  const next = new Set(deletedOriginalIds)
  const stored = deletedRegistry.get(asset)
  let changed = true
  if (stored && stored.size === next.size) {
    changed = false
    for (const value of next) {
      if (!stored.has(value)) {
        changed = true
        break
      }
    }
    if (!changed) {
      for (const value of stored) {
        if (!next.has(value)) {
          changed = true
          break
        }
      }
    }
  }

  if (!changed) {
    return
  }

  deletedRegistry.set(asset, next)
  if (emptyDeletedCache.has(asset)) {
    emptyDeletedCache.delete(asset)
  }
  notify()
}

export function getManualDeletedOriginalIdsForAsset(
  asset: ManualPositionAsset,
): Set<string> {
  const stored = deletedRegistry.get(asset)
  if (stored) {
    return stored
  }
  if (!emptyDeletedCache.has(asset)) {
    emptyDeletedCache.set(asset, new Set())
  }
  return emptyDeletedCache.get(asset) as Set<string>
}

export function useManualDeletedOriginalIds(
  asset: ManualPositionAsset,
): Set<string> {
  return useSyncExternalStore(
    listener => {
      listeners.add(listener)
      return () => {
        listeners.delete(listener)
      }
    },
    () => getManualDeletedOriginalIdsForAsset(asset),
    () => getManualDeletedOriginalIdsForAsset(asset),
  )
}
