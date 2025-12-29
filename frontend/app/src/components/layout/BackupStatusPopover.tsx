import { useCallback, useEffect, useRef, useState } from "react"
import {
  RefreshCw,
  Cloud,
  CloudAlert,
  CloudCheck,
  CloudDownload,
  CloudOff,
  CloudUpload,
  Download,
  Upload,
} from "lucide-react"
import { Button } from "@/components/ui/Button"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { useI18n } from "@/i18n"
import { useCloud } from "@/context/CloudContext"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useAppContext } from "@/context/AppContext"
import { getBackupsInfo, importBackup, uploadBackup } from "@/services/api"
import {
  BackupFileType,
  BackupMode,
  BackupSyncResult,
  FullBackupsInfo,
  FullBackupInfo,
  SyncStatus,
} from "@/types"
import { cn } from "@/lib/utils"
import { formatTimeAgo } from "@/lib/timeUtils"
import { ApiErrorException } from "@/utils/apiErrors"

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

interface BackupStatusPopoverProps {
  collapsed: boolean
}

function getStatusColor(status: SyncStatus): string {
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

function getOverallStatus(backups: FullBackupsInfo | null): SyncStatus | null {
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

function getLastRemoteBackupDate(
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

export function BackupStatusPopover({ collapsed }: BackupStatusPopoverProps) {
  const { t } = useI18n()
  const { permissions, backupMode, setBackupMode, isInitialized } = useCloud()
  const { refreshData, refreshRealEstate, refreshFlows } = useFinancialData()
  const { fetchEntities, fetchSettings } = useAppContext()

  const backupEnabled = backupMode !== BackupMode.OFF
  const isManualMode = backupMode === BackupMode.MANUAL
  const hasBackupInfo = permissions.includes("backup.info")

  const [backups, setBackups] = useState<FullBackupsInfo | null>(null)
  const [lastBackupsFetchAt, setLastBackupsFetchAt] = useState<number | null>(
    () => getPersistedLastFetchAt(),
  )
  const [isLoading, setIsLoading] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [isImporting, setIsImporting] = useState(false)
  const [isSyncing, setIsSyncing] = useState(false)
  const [isOpen, setIsOpen] = useState(false)
  const [cooldownUntil, setCooldownUntil] = useState<number | null>(null)
  const [syncCooldownUntil, setSyncCooldownUntil] = useState<number | null>(
    null,
  )
  const [statusMessage, setStatusMessage] = useState<string | null>(null)

  const backupsRef = useRef<FullBackupsInfo | null>(null)
  const skipFastCheckUntilRef = useRef<number>(0)
  const lastBootstrappedModeRef = useRef<BackupMode | null>(null)
  const autoSyncInFlightRef = useRef(false)
  const isConflictRef = useRef(false)
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
    skipFastCheckUntilRef.current = now + SKIP_FAST_CHECK_AFTER_REFRESH_MS
  }, [])

  const fetchBackups = useCallback(
    async (onlyLocal: boolean = false) => {
      if (!canAttemptNetworkNow()) {
        return
      }

      if (autoSyncInFlightRef.current) {
        return
      }

      if (!onlyLocal) {
        setIsLoading(true)
        setStatusMessage(null)
      }
      try {
        const data = await getBackupsInfo(
          onlyLocal ? { only_local: true } : undefined,
        )
        registerNetworkSuccess()

        if (onlyLocal) {
          setBackups(prev => {
            if (!prev) return normalizeBackupsInfo(data)
            const merged = { ...prev, pieces: { ...prev.pieces } }
            for (const [type, piece] of Object.entries(data.pieces)) {
              const key = type as BackupFileType
              const prevPiece = prev.pieces[key]

              // When doing a fast check, never expand the known set of pieces.
              // The backend may return null status/remote in only_local mode.
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
          skipFastCheckUntilRef.current = now + SKIP_FAST_CHECK_AFTER_REFRESH_MS
        }
      } catch (error) {
        console.error("Failed to fetch backup info:", error)
        registerNetworkFailure()
      } finally {
        if (!onlyLocal) {
          setIsLoading(false)
        }
      }
    },
    [canAttemptNetworkNow, registerNetworkFailure, registerNetworkSuccess],
  )

  useEffect(() => {
    if (!isOpen || !backupEnabled || !hasBackupInfo) return
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
      if (now < skipFastCheckUntilRef.current) return
      fetchBackups(true)
    }
  }, [
    isOpen,
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

  const isConflict = conflictTypes.length > 0

  useEffect(() => {
    isConflictRef.current = isConflict
  }, [isConflict])

  const actionInFlight = isUploading || isImporting || isSyncing
  const baseActionsDisabled =
    !backupEnabled || actionInFlight || isCooldownActive

  const handleUpload = async (types: BackupFileType[]) => {
    setIsUploading(true)
    setStatusMessage(null)
    try {
      const result = await uploadBackup({
        types,
        force: true,
      })
      applySyncResult(result)
    } catch (error) {
      console.error("Failed to upload backup:", error)
      if (
        error instanceof ApiErrorException &&
        error.code === "TOO_MANY_REQUESTS"
      ) {
        setCooldownUntil(Date.now() + 30_000)
        setStatusMessage(t.settings.backup.tooManyRequests)
      } else if (
        error instanceof ApiErrorException &&
        error.code === "CONFLICT"
      ) {
        setStatusMessage(t.settings.backup.conflictRetry)
      }
    } finally {
      setIsUploading(false)
    }
  }

  const handleImport = async (types: BackupFileType[]) => {
    setIsImporting(true)
    setStatusMessage(null)
    try {
      const result = await importBackup({
        types,
        force: true,
      })
      applySyncResult(result)
      // Reload all app data after import (same as completing an entity fetch)
      await Promise.all([
        fetchEntities(),
        fetchSettings(),
        refreshData(),
        refreshRealEstate(),
        refreshFlows(),
      ])
    } catch (error) {
      console.error("Failed to import backup:", error)
      if (
        error instanceof ApiErrorException &&
        error.code === "TOO_MANY_REQUESTS"
      ) {
        setCooldownUntil(Date.now() + 30_000)
        setStatusMessage(t.settings.backup.tooManyRequests)
      } else if (
        error instanceof ApiErrorException &&
        error.code === "CONFLICT"
      ) {
        setStatusMessage(t.settings.backup.conflictRetry)
      }
    } finally {
      setIsImporting(false)
    }
  }

  const runManualSync = useCallback(async () => {
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
      skipFastCheckUntilRef.current = now + SKIP_FAST_CHECK_AFTER_REFRESH_MS

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
        // Reload all app data after import (same as completing an entity fetch)
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
      if (
        error instanceof ApiErrorException &&
        error.code === "TOO_MANY_REQUESTS"
      ) {
        setCooldownUntil(Date.now() + 30_000)
        setStatusMessage(t.settings.backup.tooManyRequests)
      } else if (
        error instanceof ApiErrorException &&
        error.code === "CONFLICT"
      ) {
        setStatusMessage(t.settings.backup.conflictRetry)
      }
    } finally {
      setIsSyncing(false)
    }
  }, [
    canCreateBackup,
    canImportBackup,
    applySyncResult,
    fetchBackups,
    setBackups,
    setCooldownUntil,
    fetchEntities,
    fetchSettings,
    refreshData,
    refreshRealEstate,
    refreshFlows,
    registerNetworkFailure,
    registerNetworkSuccess,
  ])

  // Silent auto-sync for AUTO mode (same logic as manual sync but without UI feedback)
  const runAutoSync = useCallback(async () => {
    if (!canAttemptNetworkNow()) {
      window.dispatchEvent(
        new CustomEvent("backup-auto-sync-complete", {
          detail: { hadTransfer: false },
        }),
      )
      return
    }
    if (isConflict) {
      window.dispatchEvent(
        new CustomEvent("backup-auto-sync-complete", {
          detail: { hadTransfer: false },
        }),
      )
      return
    }
    if (isSyncing || isUploading || isImporting) return
    if (autoSyncInFlightRef.current) return

    try {
      autoSyncInFlightRef.current = true
      setIsSyncing(true)
      const info = normalizeBackupsInfo(await getBackupsInfo())
      registerNetworkSuccess()
      setBackups(info)
      const now = Date.now()
      setLastBackupsFetchAt(now)
      setPersistedLastFetchAt(now)
      skipFastCheckUntilRef.current = now + SKIP_FAST_CHECK_AFTER_REFRESH_MS

      const hasConflict = Object.values(info.pieces).some(
        piece => piece.status === SyncStatus.CONFLICT,
      )
      if (hasConflict) {
        // Dispatch event so entity fetch proceeds with normal delay
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
        await Promise.all([
          fetchEntities(),
          fetchSettings(),
          refreshData(),
          refreshRealEstate(),
          refreshFlows(),
        ])
      }

      // Dispatch event so EntityWorkflowContext can proceed with appropriate delay
      window.dispatchEvent(
        new CustomEvent("backup-auto-sync-complete", {
          detail: { hadTransfer },
        }),
      )
    } catch (error) {
      console.error("Auto sync failed:", error)
      registerNetworkFailure()
      // Dispatch event even on error so entity fetch isn't blocked
      window.dispatchEvent(
        new CustomEvent("backup-auto-sync-complete", {
          detail: { hadTransfer: false },
        }),
      )
    } finally {
      setIsSyncing(false)
      autoSyncInFlightRef.current = false
    }
  }, [
    canAttemptNetworkNow,
    isConflict,
    isSyncing,
    isUploading,
    isImporting,
    autoSyncInFlightRef,
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

  // Initial fetch when cloud context initializes with backup permission
  // For AUTO mode: run auto sync immediately (with localStorage guard to avoid retriggering)
  useEffect(() => {
    if (!isInitialized || !hasBackupInfo || !backupEnabled) return

    const isAutoMode = backupMode === BackupMode.AUTO

    // Skip if we already bootstrapped for this mode (unless switching TO AUTO)
    if (lastBootstrappedModeRef.current === backupMode) return
    if (lastBootstrappedModeRef.current !== null && !isAutoMode) {
      // Switching from AUTO to MANUAL/OFF - no need to re-bootstrap
      lastBootstrappedModeRef.current = backupMode
      return
    }
    lastBootstrappedModeRef.current = backupMode

    if (isAutoMode) {
      // Check if we already synced recently (within the interval)
      const lastAutoSync = localStorage.getItem(LAST_AUTO_SYNC_KEY)
      const now = Date.now()
      if (lastAutoSync) {
        const elapsed = now - parseInt(lastAutoSync, 10)
        if (elapsed < AUTO_SYNC_INTERVAL_MS) {
          // Already synced recently, just fetch info and dispatch event for entity fetch
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
      // Run auto sync and record the time
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

  // Auto backup intervals based on backup mode
  useEffect(() => {
    if (!isInitialized || !hasBackupInfo || !backupEnabled) return

    const isAutoMode = backupMode === BackupMode.AUTO

    if (isAutoMode) {
      // AUTO mode: sync every 10 minutes
      const autoSyncInterval = window.setInterval(() => {
        if (isConflictRef.current) return
        runAutoSync()
      }, AUTO_SYNC_INTERVAL_MS)

      return () => {
        window.clearInterval(autoSyncInterval)
      }
    } else {
      // MANUAL mode: full check every 10 min, fast check every 2.5 min
      const fullCheckInterval = window.setInterval(() => {
        if (isConflictRef.current) return
        fetchBackups(false)
      }, MANUAL_FULL_CHECK_INTERVAL_MS)

      const fastCheckInterval = window.setInterval(() => {
        if (isConflictRef.current) return
        const now = Date.now()
        if (now >= skipFastCheckUntilRef.current) {
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
    (isManualMode || isConflict) && (isCooldownActive || isSyncCooldownActive)
      ? t.settings.backup.cooldownActive
      : null
  const feedbackMessage = statusMessage ?? derivedCooldownMessage
  const getDotColor = () => {
    if (!backupEnabled) return null

    switch (overallStatus) {
      case SyncStatus.PENDING:
        return "bg-foreground"
      case SyncStatus.CONFLICT:
        return "bg-red-500"
      case SyncStatus.OUTDATED:
        return "bg-amber-500"
      default:
        return null
    }
  }

  const dotColor = getDotColor()

  const getStatusIcon = () => {
    if (isSyncing) {
      return <RefreshCw size={18} strokeWidth={2.5} className="animate-spin" />
    }

    if (!backupEnabled) {
      return <CloudOff size={18} strokeWidth={2.5} />
    }

    switch (overallStatus) {
      case SyncStatus.SYNC:
        return <CloudCheck size={18} strokeWidth={2.5} />
      case SyncStatus.PENDING:
        return <CloudUpload size={18} strokeWidth={2.5} />
      case SyncStatus.CONFLICT:
        return <CloudAlert size={18} strokeWidth={2.5} />
      case SyncStatus.OUTDATED:
        return <CloudDownload size={18} strokeWidth={2.5} />
      case SyncStatus.MISSING:
        return <Cloud size={18} strokeWidth={2.5} />
      default:
        return <Cloud size={18} strokeWidth={2.5} />
    }
  }

  const setMode = (mode: BackupMode) => {
    setBackupMode(mode)
  }

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size={collapsed ? "icon" : "sm"}
          className={cn("relative", collapsed ? "w-full" : "flex-1")}
          aria-label={
            isSyncing ? t.settings.backup.syncing : t.settings.backup.title
          }
        >
          {getStatusIcon()}
          {dotColor && (
            <span
              className={cn(
                "absolute top-1 right-1 h-1.5 w-1.5 rounded-full",
                dotColor,
              )}
            />
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent
        side={collapsed ? "right" : "top"}
        align="start"
        className="w-64 p-3"
      >
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold">{t.settings.backup.title}</h4>
            <div
              className="inline-flex items-center rounded-full border border-border bg-muted/30 p-0.5"
              role="tablist"
              aria-label={t.settings.backup.enableLabel}
            >
              <button
                type="button"
                role="tab"
                aria-selected={backupMode === BackupMode.OFF}
                onClick={() => setMode(BackupMode.OFF)}
                disabled={isLoading || actionInFlight}
                className={cn(
                  "h-7 rounded-full px-2 text-xs font-medium transition-colors",
                  backupMode === BackupMode.OFF
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {t.settings.backup.modes[BackupMode.OFF]}
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={backupMode === BackupMode.AUTO}
                onClick={() => setMode(BackupMode.AUTO)}
                disabled={isLoading || actionInFlight}
                className={cn(
                  "h-7 rounded-full px-2 text-xs font-medium transition-colors",
                  backupMode === BackupMode.AUTO
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {t.settings.backup.modes[BackupMode.AUTO]}
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={backupMode === BackupMode.MANUAL}
                onClick={() => setMode(BackupMode.MANUAL)}
                disabled={isLoading || actionInFlight}
                className={cn(
                  "h-7 rounded-full px-2 text-xs font-medium transition-colors",
                  backupMode === BackupMode.MANUAL
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {t.settings.backup.modes[BackupMode.MANUAL]}
              </button>
            </div>
          </div>

          {!backupEnabled ? null : isLoading && !backups ? (
            <div className="flex justify-center py-4">
              <LoadingSpinner size="sm" />
            </div>
          ) : backups ? (
            <>
              <div className="flex items-center justify-between">
                <div className="flex flex-col">
                  <span className="text-sm font-medium">
                    {t.settings.backup.lastBackup}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {lastBackupDate
                      ? formatTimeAgo(lastBackupDate, t)
                      : t.settings.backup.never}
                  </span>
                </div>
                {overallStatus ? (
                  <span
                    className={cn(
                      "text-xs font-medium",
                      getStatusColor(overallStatus),
                    )}
                  >
                    {overallStatus === SyncStatus.PENDING
                      ? t.settings.backup.pendingBackup
                      : t.settings.backup.status[overallStatus]}
                  </span>
                ) : null}
              </div>

              {isConflict ? (
                <div className="relative pt-1">
                  <div className="flex gap-2">
                    {canImportBackup ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="flex-1 gap-1.5"
                        onClick={() => handleImport(conflictTypes)}
                        disabled={baseActionsDisabled}
                      >
                        <Download size={14} />
                        {t.settings.backup.useRemote}
                      </Button>
                    ) : null}
                    {canCreateBackup ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="flex-1 gap-1.5"
                        onClick={() => handleUpload(conflictTypes)}
                        disabled={baseActionsDisabled}
                      >
                        <Upload size={14} />
                        {t.settings.backup.useLocal}
                      </Button>
                    ) : null}
                  </div>
                  {feedbackMessage ? (
                    <div className="absolute inset-0 flex items-center justify-center bg-background/80 backdrop-blur-sm rounded-md">
                      <p className="text-xs text-muted-foreground px-2 text-center">
                        {feedbackMessage}
                      </p>
                    </div>
                  ) : null}
                </div>
              ) : isManualMode && (canCreateBackup || canImportBackup) ? (
                <div className="relative pt-1">
                  <div className="flex">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="flex-1 gap-1.5"
                      onClick={runManualSync}
                      disabled={
                        !backupEnabled ||
                        actionInFlight ||
                        isCooldownActive ||
                        isSyncCooldownActive
                      }
                    >
                      <RefreshCw size={14} />
                      {isSyncing
                        ? t.settings.backup.syncing
                        : t.settings.backup.sync}
                    </Button>
                  </div>
                  {feedbackMessage ? (
                    <div className="absolute inset-0 flex items-center justify-center bg-background/80 backdrop-blur-sm rounded-md">
                      <p className="text-xs text-muted-foreground px-2 text-center">
                        {feedbackMessage}
                      </p>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </>
          ) : (
            <p className="text-sm text-muted-foreground text-center py-2">
              {t.settings.backup.noBackups}
            </p>
          )}
        </div>
      </PopoverContent>
    </Popover>
  )
}
