import type { ManualPositionDraft } from "./manualPositionTypes"

export interface ManualDisplayItem<
  TPosition,
  TDraft extends ManualPositionDraft<any>,
> {
  key: string
  position: TPosition
  manualDraft?: TDraft
  isManual: boolean
  isDirty: boolean
  isNew: boolean
  originalId?: string
}

export interface ManualDisplayMergeOptions<
  TPosition,
  TDraft extends ManualPositionDraft<any>,
> {
  positions: TPosition[]
  manualDrafts: TDraft[]
  getPositionOriginalId: (position: TPosition) => string | undefined
  getDraftOriginalId: (draft: TDraft) => string | undefined
  getDraftLocalId: (draft: TDraft) => string
  buildPositionFromDraft: (draft: TDraft) => TPosition
  isManualPosition: (position: TPosition) => boolean
  isDraftDirty: (draft: TDraft) => boolean
  isEntryDeleted: (originalId: string) => boolean
  shouldIncludeDraft?: (draft: TDraft) => boolean
  getPositionKey?: (position: TPosition) => string | undefined
  mergeDraftMetadata?: (position: TPosition, draft: TDraft) => TPosition
}

export function mergeManualDisplayItems<
  TPosition,
  TDraft extends ManualPositionDraft<any>,
>({
  positions,
  manualDrafts,
  getPositionOriginalId,
  getDraftOriginalId,
  getDraftLocalId,
  buildPositionFromDraft,
  isManualPosition,
  isDraftDirty,
  isEntryDeleted,
  shouldIncludeDraft,
  getPositionKey,
  mergeDraftMetadata,
}: ManualDisplayMergeOptions<TPosition, TDraft>): Array<
  ManualDisplayItem<TPosition, TDraft>
> {
  const items: Array<ManualDisplayItem<TPosition, TDraft>> = []

  const draftsByOriginalId = new Map<string, TDraft>()
  manualDrafts.forEach(draft => {
    const originalId = getDraftOriginalId(draft)
    if (originalId) {
      draftsByOriginalId.set(originalId, draft)
    }
  })

  const handledDraftLocalIds = new Set<string>()

  positions.forEach(position => {
    const originalId = getPositionOriginalId(position)
    if (originalId && isEntryDeleted(originalId)) {
      return
    }

    const draft = originalId ? draftsByOriginalId.get(originalId) : undefined

    let resolvedPosition = position
    let isDirty = false

    if (draft) {
      handledDraftLocalIds.add(getDraftLocalId(draft))
      if (isDraftDirty(draft)) {
        resolvedPosition = buildPositionFromDraft(draft)
        isDirty = true
      } else if (mergeDraftMetadata) {
        resolvedPosition = mergeDraftMetadata(position, draft)
      }
    }

    const key =
      getPositionKey?.(resolvedPosition) ||
      originalId ||
      (draft ? getDraftLocalId(draft) : undefined) ||
      `${Math.random()}`

    items.push({
      key,
      position: resolvedPosition,
      manualDraft: draft,
      isManual: isManualPosition(position),
      isDirty,
      isNew: false,
      originalId,
    })
  })

  manualDrafts.forEach(draft => {
    const originalId = getDraftOriginalId(draft)
    if (originalId) return
    const localId = getDraftLocalId(draft)
    if (handledDraftLocalIds.has(localId)) return
    if (shouldIncludeDraft && !shouldIncludeDraft(draft)) return

    const position = buildPositionFromDraft(draft)
    items.push({
      key: localId,
      position,
      manualDraft: draft,
      isManual: true,
      isDirty: true,
      isNew: true,
    })
  })

  return items
}
