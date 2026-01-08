import { BackupSettings } from "@/domain"

export interface GetBackupSettings {
  execute(): Promise<BackupSettings>
}
