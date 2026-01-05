import { BackupInfo, BackupsInfo } from "@/domain"

export interface BackupLocalRegistry {
  getInfo(): Promise<BackupsInfo>
  insert(backups: BackupInfo[]): Promise<void>
  clear(): Promise<void>
}
