import { useBackupStatus } from "@/hooks/useBackupStatus"

export function BackupAlertSync() {
  useBackupStatus({ isActive: true })
  return null
}
