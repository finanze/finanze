import { BackupSettings } from "@/domain"

export interface SaveBackupSettings {
  execute(settings: BackupSettings): Promise<BackupSettings>
}
