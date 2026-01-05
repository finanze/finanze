import {
  BackupFileType,
  BackupInfo,
  SyncStatus,
  FullBackupInfo,
  FullBackupsInfo,
  BackupsInfoRequest,
  CloudPermission,
  BackupsInfo,
} from "@/domain"
import {
  BackupRepository,
  BackupLocalRegistry,
  CloudRegister,
  Backupable,
} from "../ports"
import { NotAuthenticated, PermissionDenied } from "@/domain/exceptions"
import { GetBackups } from "@/domain/usecases"

export class GetBackupsImpl implements GetBackups {
  constructor(
    private backupablePorts: Map<BackupFileType, Backupable>,
    private backupRepository: BackupRepository,
    private backupLocalRegistry: BackupLocalRegistry,
    private cloudRegister: CloudRegister,
  ) {}

  async execute(request: BackupsInfoRequest): Promise<FullBackupsInfo> {
    const auth = await this.cloudRegister.getAuth()

    if (!auth) {
      throw new NotAuthenticated()
    }

    if (!auth.permissions?.includes(CloudPermission.BACKUP_INFO)) {
      throw new PermissionDenied(CloudPermission.BACKUP_INFO)
    }

    const localBkgInfo = await this.backupLocalRegistry.getInfo()
    let remoteBkgInfo = { pieces: {} } as BackupsInfo

    if (!request.onlyLocal) {
      remoteBkgInfo = await this.backupRepository.getInfo({
        auth: auth,
      })
    }

    const fullBackupPieces = {} as Record<BackupFileType, FullBackupInfo>

    for (const backupType of Object.values(BackupFileType)) {
      const backupable = this.backupablePorts.get(backupType)

      if (!backupable) {
        fullBackupPieces[backupType] = {
          local: localBkgInfo.pieces[backupType] ?? null,
          remote: request.onlyLocal
            ? null
            : remoteBkgInfo.pieces[backupType] || null,
          lastUpdate: "",
          hasLocalChanges: false,
          status: request.onlyLocal ? null : SyncStatus.MISSING,
        }
        continue
      }

      const lastUpdate = await backupable.getLastUpdated()
      const localBackup = localBkgInfo.pieces[backupType] ?? null
      const remoteBackup = remoteBkgInfo.pieces[backupType] || null

      const { status, hasLocalChanges } = this.calculateSyncStatus(
        localBackup,
        remoteBackup,
        lastUpdate,
      )

      fullBackupPieces[backupType] = {
        local: localBackup,
        remote: request.onlyLocal ? null : remoteBackup,
        lastUpdate: lastUpdate ? lastUpdate.toISOString() : "",
        hasLocalChanges,
        status: request.onlyLocal ? null : status,
      }
    }

    return { pieces: fullBackupPieces }
  }

  private statusForBothExist(
    local: BackupInfo,
    remote: BackupInfo,
    hasLocalChanges: boolean,
  ): SyncStatus {
    // Same backup on both sides
    if (local.id === remote.id) {
      return hasLocalChanges ? SyncStatus.PENDING : SyncStatus.SYNC
    }

    const localDate = new Date(local.date)
    const remoteDate = new Date(remote.date)

    // Different backups - need to determine relationship
    if (localDate > remoteDate) {
      // Our backup is newer (remote rolled back somehow - need to re-upload)
      return SyncStatus.PENDING
    }

    if (localDate < remoteDate) {
      // Remote is newer
      return hasLocalChanges ? SyncStatus.CONFLICT : SyncStatus.OUTDATED
    }

    // Same date but different IDs - unusual, treat as conflict
    return SyncStatus.CONFLICT
  }

  private calculateSyncStatus(
    local: BackupInfo | null,
    remote: BackupInfo | null,
    lastUpdate: Date | null,
  ): { status: SyncStatus; hasLocalChanges: boolean } {
    const localDate = local ? new Date(local.date) : null
    const hasLocalChanges =
      localDate === null || (lastUpdate !== null && lastUpdate > localDate)

    // No backups exist at all
    if (local === null && remote === null) {
      return {
        status: hasLocalChanges ? SyncStatus.PENDING : SyncStatus.MISSING,
        hasLocalChanges,
      }
    }

    // Only local backup exists (remote was deleted - need to re-upload)
    if (remote === null) {
      return { status: SyncStatus.PENDING, hasLocalChanges }
    }

    // Only remote backup exists
    if (lastUpdate === null || local === null) {
      return {
        status: hasLocalChanges ? SyncStatus.CONFLICT : SyncStatus.OUTDATED,
        hasLocalChanges,
      }
    }

    // Both local and remote backups exist
    return {
      status: this.statusForBothExist(local, remote, hasLocalChanges),
      hasLocalChanges,
    }
  }
}
