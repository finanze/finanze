import { useCallback, useEffect, useRef, useState } from "react"
import { useCloud } from "@/context/CloudContext"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useAppContext } from "@/context/AppContext"
import { useBackupAlertUpdater } from "@/context/BackupAlertContext"
import { getBackupsInfo, importBackup, uploadBackup } from "@/services/api"
import {
  BackupFileType,
  BackupMode,
  BackupSyncResult,
  FullBackupsInfo,
  FullBackupInfo,
  SyncStatus,
} from "@/types"
import { ApiErrorException } from "@/utils/apiErrors"
import { useI18n } from "@/i18n"

function getErrorCode(error: unknown): string | null {
  if (error instanceof ApiErrorException) {
    return error.code
  }
  if (
    error &&
    typeof error === "object" &&
    "code" in error &&
    typeof (error as { code: unknown }).code === "string"
  ) {
    return (error as { code: string }).code
  }
  return null
}

const LAST_BACKUP_FETCH_KEY = "backup_last_fetch_at"
const LAST_AUTO_SYNC_KEY = "backup_last_auto_sync_at"
export const LAST_AUTO_SYNC_HAD_TRANSFER_KEY =
  "backup_last_auto_sync_had_transfer"
const BACKUP_CACHE_DURATION = 3 * 60_000
const SKIP_FAST_CHECK_AFTER_REFRESH_MS = 10_000
const AUTO_SYNC_INTERVAL_MS = 10 * 60_000
const MANUAL_FULL_CHECK_INTERVAL_MS = 10 * 60_000
const MANUAL_FAST_CHECK_INTERVAL_MS = 2.5 * 60_000
const BACKUP_ERROR_BACKOFF_BASE_MS = 5_000
const BACKUP_ERROR_BACKOFF_MAX_MS = 60_000

let globalFetchInFlight = false
let globalFetchPromise: Promise<FullBackupsInfo | null> | null = null
let globalBackupsCache: FullBackupsInfo | null = null
let globalLastFetchAt: number | null = null
let globalHasCredentialsMismatch = false
let globalAutoSyncInFlight = false
let globalManualSyncInFlight = false
let globalCooldownUntil: number | null = null
let globalSyncCooldownUntil: number | null = null
let globalSkipFastCheckUntil = 0

export function resetBackupStatusCache(): void {
  globalFetchInFlight = false
  globalFetchPromise = null
  globalBackupsCache = null
  globalLastFetchAt = null
  globalHasCredentialsMismatch = false
  globalAutoSyncInFlight = false
  globalManualSyncInFlight = false
  globalCooldownUntil = null
  globalSyncCooldownUntil = null
  globalSkipFastCheckUntil = 0
  localStorage.removeItem(LAST_BACKUP_FETCH_KEY)
  localStorage.removeItem(LAST_AUTO_SYNC_KEY)
  localStorage.removeItem(LAST_AUTO_SYNC_HAD_TRANSFER_KEY)
  window.dispatchEvent(
    new CustomEvent("backup-credentials-mismatch-change", {
      detail: { hasCredentialsMismatch: false },
    }),
  )
}

const ALL_BACKUP_TYPES: BackupFileType[] = Object.values(
  BackupFileType,
) as BackupFileType[]

function createMissingPiece(): FullBackupInfo {
  return {
    local: null,
    remote: null,
    status: SyncStatus.MISSING,
    has_local_changes: false,
    last_update: new Date(0).toISOString(),
  }
}

function normalizeBackupsInfo(backups: FullBackupsInfo): {
  pieces: Record<BackupFileType, FullBackupInfo>
} {
  const rawPieces = (backups?.pieces ?? {}) as Partial<
    Record<BackupFileType, FullBackupInfo>
  >

  const pieces = {} as Record<BackupFileType, FullBackupInfo>
  for (const type of ALL_BACKUP_TYPES) {
    const maybePiece = rawPieces[type]
    pieces[type] = maybePiece ?? createMissingPiece()
  }

  return { pieces }
}

function getPersistedLastFetchAt(): number | null {
  const stored = localStorage.getItem(LAST_BACKUP_FETCH_KEY)
  if (!stored) return null
  const parsed = parseInt(stored, 10)
  return isNaN(parsed) ? null : parsed
}

function setPersistedLastFetchAt(timestamp: number): void {
  localStorage.setItem(LAST_BACKUP_FETCH_KEY, timestamp.toString())
}

export function getOverallStatus(
  backups: FullBackupsInfo | null,
): SyncStatus | null {
  if (!backups) return null

  const statuses = Object.values(backups.pieces).map(piece => piece.status)

  if (statuses.includes(SyncStatus.CONFLICT)) return SyncStatus.CONFLICT
  if (statuses.includes(SyncStatus.PENDING)) return SyncStatus.PENDING
  if (statuses.includes(SyncStatus.OUTDATED)) return SyncStatus.OUTDATED
  if (statuses.includes(SyncStatus.MISSING)) return SyncStatus.MISSING
  if (statuses.every(status => status === SyncStatus.SYNC))
    return SyncStatus.SYNC

  return null
}

export function getLastRemoteBackupDate(
  backups: FullBackupsInfo | null,
): string | null {
  if (!backups) return null

  const remoteDates = Object.values(backups.pieces)
    .map(piece => piece.remote?.date)
    .filter((date): date is string => typeof date === "string")

  if (remoteDates.length === 0) return null

  return remoteDates.reduce((latest, current) =>
    new Date(current).getTime() > new Date(latest).getTime() ? current : latest,
  )
}

export function getStatusColor(status: SyncStatus): string {
  switch (status) {
    case SyncStatus.SYNC:
      return "text-green-500"
    case SyncStatus.PENDING:
      return "text-foreground"
    case SyncStatus.CONFLICT:
      return "text-red-500"
    case SyncStatus.OUTDATED:
      return "text-amber-500"
    case SyncStatus.MISSING:
    default:
      return "text-muted-foreground"
  }
}

interface UseBackupStatusOptions {
  isActive?: boolean
}

export function useBackupStatus(options: UseBackupStatusOptions = {}) {
  const { isActive = true } = options
  const { t } = useI18n()
  const { permissions, backupMode, setBackupMode, isInitialized } = useCloud()
  const { refreshData, refreshRealEstate, refreshFlows } = useFinancialData()
  const { fetchEntities, fetchSettings } = useAppContext()
  const { updateAlertStatus } = useBackupAlertUpdater()

  const backupEnabled = backupMode !== BackupMode.OFF
  const isManualMode = backupMode === BackupMode.MANUAL
  const hasBackupInfo = permissions.includes("backup.info")

  const [backups, setBackupsState] = useState<FullBackupsInfo | null>(
    () => globalBackupsCache,
  )
  const [lastBackupsFetchAtState, setLastBackupsFetchAtState] = useState<
    number | null
  >(() => globalLastFetchAt ?? getPersistedLastFetchAt())

  const setBackups = useCallback(
    (
      value:
        | FullBackupsInfo
        | null
        | ((prev: FullBackupsInfo | null) => FullBackupsInfo | null),
    ) => {
      const next =
        typeof value === "function" ? value(globalBackupsCache) : value
      globalBackupsCache = next
      setBackupsState(next)
      window.dispatchEvent(new CustomEvent("backup-data-change"))
    },
    [],
  )

  const setLastBackupsFetchAt = useCallback((value: number | null) => {
    globalLastFetchAt = value
    setLastBackupsFetchAtState(value)
    window.dispatchEvent(new CustomEvent("backup-data-change"))
  }, [])

  const lastBackupsFetchAt = lastBackupsFetchAtState

  const [isLoading, setIsLoading] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [isImporting, setIsImporting] = useState(false)
  const [isSyncing, setIsSyncing] = useState(false)
  const [cooldownUntil, setCooldownUntilState] = useState<number | null>(
    () => globalCooldownUntil,
  )
  const [syncCooldownUntil, setSyncCooldownUntilState] = useState<
    number | null
  >(() => globalSyncCooldownUntil)

  const setCooldownUntil = useCallback((value: number | null) => {
    globalCooldownUntil = value
    setCooldownUntilState(value)
    window.dispatchEvent(new CustomEvent("backup-cooldown-change"))
  }, [])

  const setSyncCooldownUntil = useCallback((value: number | null) => {
    globalSyncCooldownUntil = value
    setSyncCooldownUntilState(value)
    window.dispatchEvent(new CustomEvent("backup-cooldown-change"))
  }, [])
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [hasCredentialsMismatch, setHasCredentialsMismatchState] = useState(
    () => globalHasCredentialsMismatch,
  )

  const setHasCredentialsMismatch = useCallback((value: boolean) => {
    globalHasCredentialsMismatch = value
    setHasCredentialsMismatchState(value)
    window.dispatchEvent(
      new CustomEvent("backup-credentials-mismatch-change", {
        detail: { hasCredentialsMismatch: value },
      }),
    )
  }, [])

  useEffect(() => {
    const handleCredentialsMismatchChange = (event: Event) => {
      const customEvent = event as CustomEvent<{
        hasCredentialsMismatch: boolean
      }>
      setHasCredentialsMismatchState(customEvent.detail.hasCredentialsMismatch)
    }
    window.addEventListener(
      "backup-credentials-mismatch-change",
      handleCredentialsMismatchChange,
    )
    return () => {
      window.removeEventListener(
        "backup-credentials-mismatch-change",
        handleCredentialsMismatchChange,
      )
    }
  }, [])

  useEffect(() => {
    const handleBackupDataChange = () => {
      setBackupsState(globalBackupsCache)
      setLastBackupsFetchAtState(globalLastFetchAt)
    }
    window.addEventListener("backup-data-change", handleBackupDataChange)
    return () => {
      window.removeEventListener("backup-data-change", handleBackupDataChange)
    }
  }, [])

  useEffect(() => {
    const handleCooldownChange = () => {
      setCooldownUntilState(globalCooldownUntil)
      setSyncCooldownUntilState(globalSyncCooldownUntil)
    }
    window.addEventListener("backup-cooldown-change", handleCooldownChange)
    return () => {
      window.removeEventListener("backup-cooldown-change", handleCooldownChange)
    }
  }, [])

  const backupsRef = useRef<FullBackupsInfo | null>(null)
  const lastBootstrappedModeRef = useRef<BackupMode | null>(null)
  const isConflictRef = useRef(false)
  const isSyncingRef = useRef(false)
  const isUploadingRef = useRef(false)
  const isImportingRef = useRef(false)
  const errorBackoffRef = useRef<{ failures: number; until: number }>({
    failures: 0,
    until: 0,
  })

  const canAttemptNetworkNow = useCallback((): boolean => {
    return Date.now() >= errorBackoffRef.current.until
  }, [])

  const registerNetworkSuccess = useCallback((): void => {
    errorBackoffRef.current.failures = 0
    errorBackoffRef.current.until = 0
  }, [])

  const registerNetworkFailure = useCallback((): void => {
    const nextFailures = Math.min(10, errorBackoffRef.current.failures + 1)
    errorBackoffRef.current.failures = nextFailures

    const delay = Math.min(
      BACKUP_ERROR_BACKOFF_MAX_MS,
      BACKUP_ERROR_BACKOFF_BASE_MS * 2 ** (nextFailures - 1),
    )
    errorBackoffRef.current.until = Date.now() + delay
  }, [])

  useEffect(() => {
    backupsRef.current = backups
  }, [backups])

  const canCreateBackup = permissions.includes("backup.create")
  const canImportBackup = permissions.includes("backup.import")

  const applySyncResult = useCallback((result: BackupSyncResult) => {
    setBackups(prev =>
      normalizeBackupsInfo({
        pieces: {
          ...(prev?.pieces ?? {}),
          ...(result.pieces as Partial<Record<BackupFileType, FullBackupInfo>>),
        } as Record<BackupFileType, FullBackupInfo>,
      }),
    )
    const now = Date.now()
    setLastBackupsFetchAt(now)
    setPersistedLastFetchAt(now)
    globalSkipFastCheckUntil = now + SKIP_FAST_CHECK_AFTER_REFRESH_MS
  }, [])

  const fetchBackups = useCallback(
    async (onlyLocal: boolean = false) => {
      if (!canAttemptNetworkNow()) {
        return
      }

      if (globalAutoSyncInFlight) {
        return
      }

      if (!onlyLocal && globalFetchInFlight) {
        if (globalFetchPromise) {
          try {
            const data = await globalFetchPromise
            if (data) {
              setBackups(normalizeBackupsInfo(data))
            }
          } catch (error) {
            console.error("Failed to join in-flight backup fetch:", error)
          }
        }
        return
      }

      if (!onlyLocal) {
        setIsLoading(true)
        setStatusMessage(null)
        globalFetchInFlight = true
      }
      try {
        const fetchPromise = getBackupsInfo(
          onlyLocal ? { only_local: true } : undefined,
        )
        if (!onlyLocal) {
          globalFetchPromise = fetchPromise
        }
        const data = await fetchPromise
        registerNetworkSuccess()

        if (onlyLocal) {
          setBackups(prev => {
            if (!prev) return normalizeBackupsInfo(data)
            const merged = { ...prev, pieces: { ...prev.pieces } }
            for (const [type, piece] of Object.entries(data.pieces)) {
              const key = type as BackupFileType
              const prevPiece = prev.pieces[key]

              if (!prevPiece) continue

              let nextStatus = prevPiece?.status
              if (piece.has_local_changes) {
                if (prevPiece?.status === SyncStatus.OUTDATED) {
                  nextStatus = SyncStatus.CONFLICT
                } else if (
                  prevPiece?.status === SyncStatus.SYNC ||
                  prevPiece?.status === SyncStatus.MISSING
                ) {
                  nextStatus = SyncStatus.PENDING
                }
              }

              merged.pieces[key] = {
                ...prevPiece,
                status: nextStatus ?? prevPiece?.status,
                has_local_changes: piece.has_local_changes,
                last_update: piece.last_update,
              }
            }
            return merged
          })
        } else {
          setBackups(normalizeBackupsInfo(data))
          const now = Date.now()
          setLastBackupsFetchAt(now)
          setPersistedLastFetchAt(now)
          globalSkipFastCheckUntil = now + SKIP_FAST_CHECK_AFTER_REFRESH_MS
          setStatusMessage(null)
        }
      } catch (error) {
        console.error("Failed to fetch backup info:", error)
        registerNetworkFailure()
      } finally {
        if (!onlyLocal) {
          setIsLoading(false)
          globalFetchInFlight = false
          globalFetchPromise = null
        }
      }
    },
    [canAttemptNetworkNow, registerNetworkFailure, registerNetworkSuccess],
  )

  useEffect(() => {
    if (!isActive || !backupEnabled || !hasBackupInfo) return
    if (isLoading) return

    const actionInFlight = isUploading || isImporting || isSyncing
    if (actionInFlight) return

    const now = Date.now()
    const isStale =
      lastBackupsFetchAt === null ||
      now - lastBackupsFetchAt >= BACKUP_CACHE_DURATION

    const currentBackups = backupsRef.current

    if (!currentBackups) {
      fetchBackups(false)
    } else if (isStale) {
      fetchBackups(false)
    } else {
      if (now < globalSkipFastCheckUntil) return
      fetchBackups(true)
    }
  }, [
    isActive,
    backupEnabled,
    hasBackupInfo,
    lastBackupsFetchAt,
    fetchBackups,
    isLoading,
    isUploading,
    isImporting,
    isSyncing,
  ])

  useEffect(() => {
    if (cooldownUntil === null) return
    const remaining = Math.max(0, cooldownUntil - Date.now())
    const timeout = window.setTimeout(() => setCooldownUntil(null), remaining)
    return () => window.clearTimeout(timeout)
  }, [cooldownUntil])

  useEffect(() => {
    if (syncCooldownUntil === null) return
    const remaining = Math.max(0, syncCooldownUntil - Date.now())
    const timeout = window.setTimeout(
      () => setSyncCooldownUntil(null),
      remaining,
    )
    return () => window.clearTimeout(timeout)
  }, [syncCooldownUntil])

  const isCooldownActive = cooldownUntil !== null && Date.now() < cooldownUntil
  const isSyncCooldownActive =
    syncCooldownUntil !== null && Date.now() < syncCooldownUntil

  const conflictTypes = backups
    ? (Object.entries(backups.pieces)
        .filter(([, piece]) => piece.status === SyncStatus.CONFLICT)
        .map(([type]) => type as BackupFileType) as BackupFileType[])
    : ([] as BackupFileType[])

  const conflictImportTypes = backups
    ? (Object.entries(backups.pieces)
        .filter(
          ([, piece]) =>
            piece.status === SyncStatus.CONFLICT ||
            piece.status === SyncStatus.OUTDATED,
        )
        .map(([type]) => type as BackupFileType) as BackupFileType[])
    : ([] as BackupFileType[])

  const conflictUploadTypes = backups
    ? (Object.entries(backups.pieces)
        .filter(
          ([, piece]) =>
            piece.status === SyncStatus.CONFLICT ||
            piece.status === SyncStatus.PENDING ||
            piece.status === SyncStatus.MISSING,
        )
        .map(([type]) => type as BackupFileType) as BackupFileType[])
    : ([] as BackupFileType[])

  const isConflict = conflictTypes.length > 0

  useEffect(() => {
    isConflictRef.current = isConflict
  }, [isConflict])

  useEffect(() => {
    isSyncingRef.current = isSyncing
  }, [isSyncing])

  useEffect(() => {
    isUploadingRef.current = isUploading
  }, [isUploading])

  useEffect(() => {
    isImportingRef.current = isImporting
  }, [isImporting])

  const actionInFlight = isUploading || isImporting || isSyncing
  const baseActionsDisabled =
    !backupEnabled || actionInFlight || isCooldownActive

  const handleUpload = async (types: BackupFileType[]) => {
    setIsUploading(true)
    setStatusMessage(null)
    try {
      const outdatedTypes = backupsRef.current
        ? Object.entries(backupsRef.current.pieces)
            .filter(([, piece]) => piece.status === SyncStatus.OUTDATED)
            .map(([type]) => type as BackupFileType)
        : []

      const result = await uploadBackup({
        types,
        force: true,
      })
      applySyncResult(result)

      if (outdatedTypes.length > 0 && canImportBackup) {
        try {
          const importResult = await importBackup({ types: outdatedTypes })
          applySyncResult(importResult)
          setHasCredentialsMismatch(false)
          await Promise.all([
            fetchEntities(),
            fetchSettings(),
            refreshData(),
            refreshRealEstate(),
            refreshFlows(),
          ])
        } catch (followUpError) {
          console.error(
            "Failed to import outdated pieces after upload:",
            followUpError,
          )
        }
      }

      registerNetworkSuccess()
    } catch (error) {
      console.error("Failed to upload backup:", error)
      registerNetworkFailure()
      const errorCode = getErrorCode(error)
      if (errorCode === "TOO_MANY_REQUESTS") {
        setCooldownUntil(Date.now() + 30_000)
        setStatusMessage(t.settings.backup.tooManyRequests)
      } else if (errorCode === "CONFLICT") {
        setStatusMessage(t.settings.backup.conflictRetry)
      } else if (errorCode === "INVALID_BACKUP_CREDENTIALS") {
        setHasCredentialsMismatch(true)
      }
    } finally {
      setIsUploading(false)
    }
  }

  const handleImport = async (types: BackupFileType[]) => {
    setIsImporting(true)
    setStatusMessage(null)
    try {
      const pendingTypes = backupsRef.current
        ? Object.entries(backupsRef.current.pieces)
            .filter(
              ([, piece]) =>
                piece.status === SyncStatus.PENDING ||
                piece.status === SyncStatus.MISSING,
            )
            .map(([type]) => type as BackupFileType)
        : []

      const result = await importBackup({
        types,
        force: true,
      })
      applySyncResult(result)
      setHasCredentialsMismatch(false)
      try {
        const refreshed = normalizeBackupsInfo(await getBackupsInfo())
        setBackups(refreshed)
        const now = Date.now()
        setLastBackupsFetchAt(now)
        setPersistedLastFetchAt(now)
        globalSkipFastCheckUntil = now + SKIP_FAST_CHECK_AFTER_REFRESH_MS
      } catch (refreshError) {
        console.error(
          "Failed to refresh backup info after import:",
          refreshError,
        )
      }
      try {
        await Promise.all([
          fetchEntities(),
          fetchSettings(),
          refreshData(),
          refreshRealEstate(),
          refreshFlows(),
        ])
      } catch (refreshError) {
        console.error("Failed to refresh data after import:", refreshError)
      }

      if (pendingTypes.length > 0 && canCreateBackup) {
        try {
          const uploadResult = await uploadBackup({ types: pendingTypes })
          applySyncResult(uploadResult)
        } catch (followUpError) {
          console.error(
            "Failed to upload pending pieces after import:",
            followUpError,
          )
        }
      }

      registerNetworkSuccess()
    } catch (error) {
      console.error("Failed to import backup:", error)
      registerNetworkFailure()
      const errorCode = getErrorCode(error)
      if (errorCode === "TOO_MANY_REQUESTS") {
        setCooldownUntil(Date.now() + 30_000)
        setStatusMessage(t.settings.backup.tooManyRequests)
      } else if (errorCode === "CONFLICT") {
        setStatusMessage(t.settings.backup.conflictRetry)
      } else if (errorCode === "INVALID_BACKUP_CREDENTIALS") {
        setHasCredentialsMismatch(true)
      }
    } finally {
      setIsImporting(false)
    }
  }

  const runManualSync = useCallback(async () => {
    if (globalManualSyncInFlight || globalAutoSyncInFlight) return
    globalManualSyncInFlight = true
    setIsSyncing(true)
    setSyncCooldownUntil(Date.now() + 5 * 60_000)
    setStatusMessage(null)

    try {
      const info = normalizeBackupsInfo(await getBackupsInfo())
      registerNetworkSuccess()
      setBackups(info)
      const now = Date.now()
      setLastBackupsFetchAt(now)
      setPersistedLastFetchAt(now)
      globalSkipFastCheckUntil = now + SKIP_FAST_CHECK_AFTER_REFRESH_MS

      const hasConflict = Object.values(info.pieces).some(
        piece => piece.status === SyncStatus.CONFLICT,
      )
      if (hasConflict) return

      const toUpload: BackupFileType[] = []
      const toImport: BackupFileType[] = []

      for (const [type, piece] of Object.entries(info.pieces) as Array<
        [BackupFileType, FullBackupsInfo["pieces"][BackupFileType]]
      >) {
        if (
          piece.status === SyncStatus.PENDING ||
          piece.status === SyncStatus.MISSING
        ) {
          if (canCreateBackup) toUpload.push(type)
        }
        if (piece.status === SyncStatus.OUTDATED) {
          if (canImportBackup) toImport.push(type)
        }
      }

      if (toUpload.length > 0) {
        const uploadResult = await uploadBackup({ types: toUpload })
        applySyncResult(uploadResult)
      }
      if (toImport.length > 0) {
        const importResult = await importBackup({ types: toImport })
        applySyncResult(importResult)
        setHasCredentialsMismatch(false)
        await Promise.all([
          fetchEntities(),
          fetchSettings(),
          refreshData(),
          refreshRealEstate(),
          refreshFlows(),
        ])
      }
    } catch (error) {
      console.error("Failed to sync backups:", error)
      registerNetworkFailure()
      const errorCode = getErrorCode(error)
      if (errorCode === "TOO_MANY_REQUESTS") {
        setCooldownUntil(Date.now() + 30_000)
        setStatusMessage(t.settings.backup.tooManyRequests)
      } else if (errorCode === "CONFLICT") {
        setStatusMessage(t.settings.backup.conflictRetry)
      } else if (errorCode === "INVALID_BACKUP_CREDENTIALS") {
        setHasCredentialsMismatch(true)
      }
    } finally {
      setIsSyncing(false)
      globalManualSyncInFlight = false
    }
  }, [
    canCreateBackup,
    canImportBackup,
    applySyncResult,
    fetchEntities,
    fetchSettings,
    refreshData,
    refreshRealEstate,
    refreshFlows,
    registerNetworkFailure,
    registerNetworkSuccess,
    t.settings.backup.conflictRetry,
    t.settings.backup.tooManyRequests,
  ])

  const runAutoSync = useCallback(async () => {
    if (!canAttemptNetworkNow()) {
      window.dispatchEvent(
        new CustomEvent("backup-auto-sync-complete", {
          detail: { hadTransfer: false },
        }),
      )
      return
    }
    if (isConflictRef.current) {
      window.dispatchEvent(
        new CustomEvent("backup-auto-sync-complete", {
          detail: { hadTransfer: false },
        }),
      )
      return
    }
    if (
      isSyncingRef.current ||
      isUploadingRef.current ||
      isImportingRef.current
    )
      return
    if (globalAutoSyncInFlight || globalManualSyncInFlight) return

    try {
      globalAutoSyncInFlight = true
      setIsSyncing(true)
      const info = normalizeBackupsInfo(await getBackupsInfo())
      registerNetworkSuccess()
      setBackups(info)
      const now = Date.now()
      setLastBackupsFetchAt(now)
      setPersistedLastFetchAt(now)
      globalSkipFastCheckUntil = now + SKIP_FAST_CHECK_AFTER_REFRESH_MS

      const hasConflict = Object.values(info.pieces).some(
        piece => piece.status === SyncStatus.CONFLICT,
      )
      if (hasConflict) {
        window.dispatchEvent(
          new CustomEvent("backup-auto-sync-complete", {
            detail: { hadTransfer: false },
          }),
        )
        return
      }

      const toUpload: BackupFileType[] = []
      const toImport: BackupFileType[] = []

      for (const [type, piece] of Object.entries(info.pieces) as Array<
        [BackupFileType, FullBackupsInfo["pieces"][BackupFileType]]
      >) {
        if (
          piece.status === SyncStatus.PENDING ||
          piece.status === SyncStatus.MISSING
        ) {
          if (canCreateBackup) toUpload.push(type)
        }
        if (piece.status === SyncStatus.OUTDATED) {
          if (canImportBackup) toImport.push(type)
        }
      }

      const hadTransfer = toUpload.length > 0 || toImport.length > 0
      localStorage.setItem(
        LAST_AUTO_SYNC_HAD_TRANSFER_KEY,
        hadTransfer ? "1" : "0",
      )

      if (toUpload.length > 0) {
        const uploadResult = await uploadBackup({ types: toUpload })
        applySyncResult(uploadResult)
      }
      if (toImport.length > 0) {
        const importResult = await importBackup({ types: toImport })
        applySyncResult(importResult)
        setHasCredentialsMismatch(false)
        await Promise.all([
          fetchEntities(),
          fetchSettings(),
          refreshData(),
          refreshRealEstate(),
          refreshFlows(),
        ])
      }

      window.dispatchEvent(
        new CustomEvent("backup-auto-sync-complete", {
          detail: { hadTransfer },
        }),
      )
    } catch (error) {
      console.error("Auto sync failed:", error)
      registerNetworkFailure()
      const errorCode = getErrorCode(error)
      if (errorCode === "INVALID_BACKUP_CREDENTIALS") {
        setHasCredentialsMismatch(true)
      }
      window.dispatchEvent(
        new CustomEvent("backup-auto-sync-complete", {
          detail: { hadTransfer: false },
        }),
      )
    } finally {
      setIsSyncing(false)
      globalAutoSyncInFlight = false
    }
  }, [
    canAttemptNetworkNow,
    canCreateBackup,
    canImportBackup,
    applySyncResult,
    fetchEntities,
    fetchSettings,
    refreshData,
    refreshRealEstate,
    refreshFlows,
    registerNetworkFailure,
    registerNetworkSuccess,
  ])

  useEffect(() => {
    if (!isInitialized || !hasBackupInfo || !backupEnabled) return

    const isAutoMode = backupMode === BackupMode.AUTO

    if (lastBootstrappedModeRef.current === backupMode) return
    if (lastBootstrappedModeRef.current !== null && !isAutoMode) {
      lastBootstrappedModeRef.current = backupMode
      return
    }
    lastBootstrappedModeRef.current = backupMode

    if (isAutoMode) {
      const lastAutoSync = localStorage.getItem(LAST_AUTO_SYNC_KEY)
      const now = Date.now()
      if (lastAutoSync) {
        const elapsed = now - parseInt(lastAutoSync, 10)
        if (elapsed < AUTO_SYNC_INTERVAL_MS) {
          if (!backupsRef.current) {
            fetchBackups(false)
          }
          window.dispatchEvent(
            new CustomEvent("backup-auto-sync-complete", {
              detail: { hadTransfer: false },
            }),
          )
          return
        }
      }
      localStorage.setItem(LAST_AUTO_SYNC_KEY, now.toString())
      runAutoSync()
    } else {
      if (!backupsRef.current) {
        fetchBackups(false)
      }
    }
  }, [
    isInitialized,
    hasBackupInfo,
    backupEnabled,
    backupMode,
    fetchBackups,
    runAutoSync,
  ])

  useEffect(() => {
    if (!isInitialized || !hasBackupInfo || !backupEnabled) return

    const isAutoMode = backupMode === BackupMode.AUTO

    if (isAutoMode) {
      const autoSyncInterval = window.setInterval(() => {
        if (isConflictRef.current) return
        runAutoSync()
      }, AUTO_SYNC_INTERVAL_MS)

      return () => {
        window.clearInterval(autoSyncInterval)
      }
    } else {
      const fullCheckInterval = window.setInterval(() => {
        if (isConflictRef.current) return
        fetchBackups(false)
      }, MANUAL_FULL_CHECK_INTERVAL_MS)

      const fastCheckInterval = window.setInterval(() => {
        if (isConflictRef.current) return
        const now = Date.now()
        if (now >= globalSkipFastCheckUntil) {
          fetchBackups(true)
        }
      }, MANUAL_FAST_CHECK_INTERVAL_MS)

      return () => {
        window.clearInterval(fullCheckInterval)
        window.clearInterval(fastCheckInterval)
      }
    }
  }, [
    isInitialized,
    hasBackupInfo,
    backupEnabled,
    backupMode,
    runAutoSync,
    fetchBackups,
  ])

  const overallStatus = getOverallStatus(backups)
  const lastBackupDate = getLastRemoteBackupDate(backups)
  const derivedCooldownMessage =
    (isManualMode || isConflict) && isCooldownActive
      ? t.settings.backup.cooldownActive
      : null
  const feedbackMessage = statusMessage ?? derivedCooldownMessage

  useEffect(() => {
    updateAlertStatus(overallStatus, backupMode, hasCredentialsMismatch)
  }, [overallStatus, backupMode, hasCredentialsMismatch, updateAlertStatus])

  return {
    backups,
    backupEnabled,
    backupMode,
    setBackupMode,
    isManualMode,
    hasBackupInfo,
    isLoading,
    isUploading,
    isImporting,
    isSyncing,
    isCooldownActive,
    isSyncCooldownActive,
    isConflict,
    conflictTypes,
    conflictImportTypes,
    conflictUploadTypes,
    hasCredentialsMismatch,
    actionInFlight,
    baseActionsDisabled,
    overallStatus,
    lastBackupDate,
    feedbackMessage,
    canCreateBackup,
    canImportBackup,
    handleUpload,
    handleImport,
    runManualSync,
  }
}
