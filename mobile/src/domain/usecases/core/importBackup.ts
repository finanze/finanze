import { BackupSyncResult, ImportBackupRequest } from "@/domain"

export interface ImportBackup {
  execute(request: ImportBackupRequest): Promise<BackupSyncResult>
}
