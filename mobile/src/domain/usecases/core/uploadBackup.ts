import { BackupSyncResult, UploadBackupRequest } from "@/domain"

export interface UploadBackup {
  execute(request: UploadBackupRequest): Promise<BackupSyncResult>
}
