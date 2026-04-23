import {
  BackupFileType,
  type FullBackupsInfo,
  type FullBackupInfo,
  type BackupSyncResult,
  SyncStatus,
} from "@/types"

export function buildPiece(
  status: SyncStatus,
  hasLocalChanges?: boolean,
): FullBackupInfo {
  const now = new Date().toISOString()
  const localId = "local-id-1"
  const remoteId = "remote-id-1"

  const localInfo = {
    id: localId,
    protocol: 1,
    date: now,
    type: BackupFileType.DATA,
    size: 100,
  }
  const remoteInfo = {
    id: remoteId,
    protocol: 1,
    date: now,
    type: BackupFileType.DATA,
    size: 100,
  }

  const resolveHasLocalChanges = () => {
    if (hasLocalChanges !== undefined) return hasLocalChanges
    return status === SyncStatus.PENDING || status === SyncStatus.CONFLICT
  }

  switch (status) {
    case SyncStatus.SYNC:
      return {
        local: { ...localInfo, id: "same-id" },
        remote: { ...remoteInfo, id: "same-id" },
        status: SyncStatus.SYNC,
        has_local_changes: false,
        last_update: now,
      }
    case SyncStatus.PENDING:
      return {
        local: localInfo,
        remote: null,
        status: SyncStatus.PENDING,
        has_local_changes: true,
        last_update: now,
      }
    case SyncStatus.CONFLICT:
      return {
        local: localInfo,
        remote: remoteInfo,
        status: SyncStatus.CONFLICT,
        has_local_changes: true,
        last_update: now,
      }
    case SyncStatus.OUTDATED:
      return {
        local: localInfo,
        remote: remoteInfo,
        status: SyncStatus.OUTDATED,
        has_local_changes: false,
        last_update: now,
      }
    case SyncStatus.MISSING:
      return {
        local: null,
        remote: null,
        status: SyncStatus.MISSING,
        has_local_changes: false,
        last_update: now,
      }
    default:
      return {
        local: localInfo,
        remote: remoteInfo,
        status,
        has_local_changes: resolveHasLocalChanges(),
        last_update: now,
      }
  }
}

export function buildBackupsInfo(
  dataStatus: SyncStatus,
  configStatus: SyncStatus,
): FullBackupsInfo {
  return {
    pieces: {
      [BackupFileType.DATA]: buildPiece(dataStatus),
      [BackupFileType.CONFIG]: buildPiece(configStatus),
    },
  }
}

export function buildSyncResult(
  types: BackupFileType[],
  status: SyncStatus = SyncStatus.SYNC,
): BackupSyncResult {
  const pieces: Partial<Record<BackupFileType, FullBackupInfo>> = {}
  for (const type of types) {
    pieces[type] = buildPiece(status)
  }
  return { pieces } as BackupSyncResult
}
