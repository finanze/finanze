import {
  ArrowUpFromLine,
  ArrowDownToLine,
  RefreshCw,
  Loader2,
  Power,
  Zap,
  Hand,
} from "lucide-react"
import type { ReactNode } from "react"
import { Button } from "@/components/ui/Button"
import { cn } from "@/lib/utils"
import { useI18n } from "@/i18n"
import {
  BackupFileType,
  BackupMode,
  FullBackupsInfo,
  SyncStatus,
} from "@/types"
import { getStatusColor } from "@/hooks/useBackupStatus"

export function formatTimeAgo(
  date: string,
  t: ReturnType<typeof useI18n>["t"],
): string {
  const now = new Date()
  const then = new Date(date)
  const diffMs = now.getTime() - then.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)
  const diffWeeks = Math.floor(diffMs / 604800000)

  if (diffMins < 1) {
    return t.settings.backup.justNow
  } else if (diffMins < 60) {
    return diffMins === 1
      ? t.settings.backup.oneMinuteAgo
      : t.settings.backup.minutesAgo.replace("{n}", diffMins.toString())
  } else if (diffHours < 24) {
    return diffHours === 1
      ? t.settings.backup.oneHourAgo
      : t.settings.backup.hoursAgo.replace("{n}", diffHours.toString())
  } else if (diffDays < 7) {
    return diffDays === 1
      ? t.settings.backup.oneDayAgo
      : t.settings.backup.daysAgo.replace("{n}", diffDays.toString())
  } else {
    return diffWeeks === 1
      ? t.settings.backup.oneWeekAgo
      : t.settings.backup.weeksAgo.replace("{n}", diffWeeks.toString())
  }
}

function getStatusLabel(
  status: SyncStatus | null,
  t: ReturnType<typeof useI18n>["t"],
): string {
  switch (status) {
    case SyncStatus.SYNC:
      return t.settings.backup.statusSync
    case SyncStatus.PENDING:
      return t.settings.backup.statusPending
    case SyncStatus.CONFLICT:
      return t.settings.backup.statusConflict
    case SyncStatus.OUTDATED:
      return t.settings.backup.statusOutdated
    case SyncStatus.MISSING:
      return t.settings.backup.statusMissing
    default:
      return t.settings.backup.statusUnknown
  }
}

interface BackupModeOption {
  value: BackupMode
  label: string
  icon: ReactNode
}

interface BackupStatusContentProps {
  backups: FullBackupsInfo | null
  backupEnabled: boolean
  backupMode: BackupMode
  setBackupMode: (mode: BackupMode) => void
  isManualMode: boolean
  isLoading: boolean
  isUploading: boolean
  isImporting: boolean
  isSyncing: boolean
  isCooldownActive: boolean
  isSyncCooldownActive: boolean
  isConflict: boolean
  conflictTypes: BackupFileType[]
  hasCredentialsMismatch: boolean
  baseActionsDisabled: boolean
  overallStatus: SyncStatus | null
  lastBackupDate: string | null
  feedbackMessage: string | null
  canCreateBackup: boolean
  canImportBackup: boolean
  handleUpload: (types: BackupFileType[]) => Promise<void>
  handleImport: (types: BackupFileType[]) => Promise<void>
  runManualSync: () => Promise<void>
  showModeSelector?: boolean
  className?: string
}

export function BackupStatusContent({
  backups,
  backupEnabled,
  backupMode,
  setBackupMode,
  isManualMode,
  isLoading,
  isUploading,
  isImporting,
  isSyncing,
  isCooldownActive,
  isSyncCooldownActive,
  isConflict,
  conflictTypes,
  hasCredentialsMismatch,
  baseActionsDisabled,
  overallStatus,
  lastBackupDate,
  feedbackMessage,
  canCreateBackup,
  canImportBackup,
  handleUpload,
  handleImport,
  runManualSync,
  showModeSelector = true,
  className,
}: BackupStatusContentProps) {
  const { t } = useI18n()

  const backupModeOptions: BackupModeOption[] = [
    {
      value: BackupMode.OFF,
      label: t.settings.backup.modes.OFF,
      icon: <Power className="h-4 w-4" />,
    },
    {
      value: BackupMode.AUTO,
      label: t.settings.backup.auto,
      icon: <Zap className="h-4 w-4" />,
    },
    {
      value: BackupMode.MANUAL,
      label: t.settings.backup.manual,
      icon: <Hand className="h-4 w-4" />,
    },
  ]

  const ALL_BACKUP_TYPES: BackupFileType[] = Object.values(
    BackupFileType,
  ) as BackupFileType[]

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      {showModeSelector && (
        <div className="flex flex-col gap-2">
          <div className="mx-auto w-full max-w-2xl">
            <div className="flex w-full items-center gap-1 rounded-lg bg-muted p-1">
              {backupModeOptions.map(({ value, label, icon }) => (
                <button
                  key={value}
                  onClick={() => setBackupMode(value)}
                  className={cn(
                    "flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                    backupMode === value
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {icon}
                  <span>{label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {backupEnabled && (
        <>
          <div className="flex items-center justify-between">
            <div className="flex flex-col gap-1">
              <span className="text-sm text-muted-foreground">
                {t.settings.backup.lastBackup}
              </span>
              {isLoading ? (
                <span className="text-sm text-muted-foreground">
                  {t.common.loading}...
                </span>
              ) : lastBackupDate ? (
                <span className="text-sm font-medium">
                  {formatTimeAgo(lastBackupDate, t)}
                </span>
              ) : (
                <span className="text-sm text-muted-foreground">
                  {t.settings.backup.noBackupYet}
                </span>
              )}
            </div>
            {!isLoading && (overallStatus || hasCredentialsMismatch) && (
              <div className="flex items-center gap-1.5">
                <span
                  className={cn(
                    "h-2 w-2 rounded-full",
                    hasCredentialsMismatch
                      ? "bg-red-700"
                      : overallStatus
                        ? getStatusColor(overallStatus).replace("text-", "bg-")
                        : "",
                  )}
                />
                <span
                  className={cn(
                    "text-xs font-medium",
                    hasCredentialsMismatch
                      ? "text-red-700"
                      : overallStatus
                        ? getStatusColor(overallStatus)
                        : "",
                  )}
                >
                  {hasCredentialsMismatch
                    ? t.settings.backup.credentialsMismatch
                    : overallStatus
                      ? getStatusLabel(overallStatus, t)
                      : ""}
                </span>
              </div>
            )}
          </div>

          {feedbackMessage && (
            <p className="text-xs text-amber-500">{feedbackMessage}</p>
          )}

          {hasCredentialsMismatch && (
            <div className="flex flex-col gap-2 rounded-md border border-red-700/30 bg-red-700/10 p-3">
              <p className="text-sm font-medium text-red-700">
                {t.settings.backup.credentialsMismatchTitle}
              </p>
              <p className="text-xs text-muted-foreground">
                {t.settings.backup.credentialsMismatchDescription}
              </p>
              <p className="text-xs text-muted-foreground italic">
                {t.settings.backup.credentialsMismatchHint}
              </p>
            </div>
          )}

          {isConflict && !hasCredentialsMismatch && (
            <div className="flex flex-col gap-2 rounded-md border border-red-500/30 bg-red-500/10 p-3">
              <p className="text-sm font-medium text-red-500">
                {t.settings.backup.conflictDetected}
              </p>
              <p className="text-xs text-muted-foreground">
                {t.settings.backup.conflictDescription}
              </p>
              <div className="flex gap-2 mt-1">
                <Button
                  variant="outline"
                  size="sm"
                  className="flex-1 text-xs"
                  disabled={
                    baseActionsDisabled || isCooldownActive || !canImportBackup
                  }
                  onClick={() => handleImport(conflictTypes)}
                >
                  {isImporting ? (
                    <Loader2 className="h-3 w-3 animate-spin mr-1" />
                  ) : (
                    <ArrowDownToLine className="h-3 w-3 mr-1" />
                  )}
                  {t.settings.backup.useRemote}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="flex-1 text-xs"
                  disabled={
                    baseActionsDisabled || isCooldownActive || !canCreateBackup
                  }
                  onClick={() => handleUpload(conflictTypes)}
                >
                  {isUploading ? (
                    <Loader2 className="h-3 w-3 animate-spin mr-1" />
                  ) : (
                    <ArrowUpFromLine className="h-3 w-3 mr-1" />
                  )}
                  {t.settings.backup.useLocal}
                </Button>
              </div>
            </div>
          )}

          {isManualMode && !isConflict && (
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              disabled={
                baseActionsDisabled ||
                isSyncCooldownActive ||
                !backups ||
                (!canCreateBackup && !canImportBackup)
              }
              onClick={runManualSync}
            >
              {isSyncing ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <RefreshCw className="h-4 w-4 mr-2" />
              )}
              {t.settings.backup.syncNow}
            </Button>
          )}

          {!isManualMode && !isConflict && (
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                className="flex-1"
                disabled={baseActionsDisabled || !backups || !canCreateBackup}
                onClick={() => handleUpload(ALL_BACKUP_TYPES)}
              >
                {isUploading ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <ArrowUpFromLine className="h-4 w-4 mr-2" />
                )}
                {t.settings.backup.upload}
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="flex-1"
                disabled={baseActionsDisabled || !backups || !canImportBackup}
                onClick={() => handleImport(ALL_BACKUP_TYPES)}
              >
                {isImporting ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <ArrowDownToLine className="h-4 w-4 mr-2" />
                )}
                {t.settings.backup.download}
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
