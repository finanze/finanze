import AsyncStorage from "@react-native-async-storage/async-storage"

import { BackupFileType, BackupInfo, BackupsInfo } from "@/domain"
import { BackupLocalRegistry } from "@/application/ports"

const STORAGE_KEY = "finanze.backupLocalRegistry.v1"

type StoredRegistry = Partial<Record<BackupFileType, BackupInfo>>

function isBackupFileType(value: string): value is BackupFileType {
  return (Object.values(BackupFileType) as string[]).includes(value)
}

export class AsyncStorageBackupLocalRegistry implements BackupLocalRegistry {
  async getInfo(): Promise<BackupsInfo> {
    try {
      const raw = await AsyncStorage.getItem(STORAGE_KEY)
      if (!raw) {
        return { pieces: {} }
      }

      const parsed = JSON.parse(raw) as Record<string, BackupInfo>
      const pieces: Partial<Record<BackupFileType, BackupInfo>> = {}

      for (const [key, value] of Object.entries(parsed)) {
        if (isBackupFileType(key) && value) {
          pieces[key] = value
        }
      }

      return { pieces }
    } catch {
      return { pieces: {} }
    }
  }

  async insert(backups: BackupInfo[]): Promise<void> {
    const current = await this.readStoredRegistry()

    for (const backup of backups) {
      current[backup.type] = backup
    }

    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(current))
  }

  async clear(): Promise<void> {
    await AsyncStorage.removeItem(STORAGE_KEY)
  }

  private async readStoredRegistry(): Promise<StoredRegistry> {
    try {
      const raw = await AsyncStorage.getItem(STORAGE_KEY)
      if (!raw) {
        return {}
      }
      const parsed = JSON.parse(raw) as Record<string, BackupInfo>

      const stored: StoredRegistry = {}
      for (const [key, value] of Object.entries(parsed)) {
        if (isBackupFileType(key) && value) {
          stored[key] = value
        }
      }

      return stored
    } catch {
      return {}
    }
  }
}
