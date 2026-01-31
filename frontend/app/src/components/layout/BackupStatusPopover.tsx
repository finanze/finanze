import { useState } from "react"
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
import { BackupMode, SyncStatus } from "@/types"
import { cn } from "@/lib/utils"
import {
  useBackupStatus,
  getStatusColor,
  LAST_AUTO_SYNC_HAD_TRANSFER_KEY,
} from "@/hooks/useBackupStatus"
import { formatTimeAgo } from "@/components/backup/BackupStatusContent"

export { LAST_AUTO_SYNC_HAD_TRANSFER_KEY }

interface BackupStatusPopoverProps {
  collapsed: boolean
}

export function BackupStatusPopover({ collapsed }: BackupStatusPopoverProps) {
  const { t } = useI18n()
  const [isOpen, setIsOpen] = useState(false)

  const {
    backups,
    backupEnabled,
    backupMode,
    setBackupMode,
    isManualMode,
    isLoading,
    isSyncing,
    isCooldownActive,
    isSyncCooldownActive,
    isConflict,
    conflictTypes,
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
  } = useBackupStatus({ isActive: isOpen })

  const getDotColor = () => {
    if (!backupEnabled) return null

    if (hasCredentialsMismatch) return "bg-red-700"

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

  const statusLabel = (() => {
    if (hasCredentialsMismatch) {
      return t.settings.backup.credentialsMismatch
    }
    if (overallStatus === SyncStatus.PENDING) {
      return t.settings.backup.pendingBackup
    }
    if (overallStatus) {
      return t.settings.backup.status[overallStatus]
    }
    return null
  })()

  const statusTextColor = hasCredentialsMismatch
    ? "text-red-700"
    : overallStatus
      ? getStatusColor(overallStatus)
      : null

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
                {statusLabel ? (
                  <span
                    className={cn(
                      "text-xs font-medium text-right",
                      statusTextColor,
                    )}
                  >
                    {statusLabel}
                  </span>
                ) : null}
              </div>

              {hasCredentialsMismatch ? (
                <div className="rounded-md border border-red-700/30 bg-red-700/10 p-2">
                  <p className="text-xs text-muted-foreground">
                    {t.settings.backup.credentialsMismatchDescription}
                  </p>
                </div>
              ) : isConflict ? (
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
