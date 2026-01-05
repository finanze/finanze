import {
  BackupFileType,
  BackupInfo,
  SyncStatus,
  FullBackupInfo,
  ImportBackupRequest,
  BackupSyncResult,
  CloudPermission,
} from "@/domain"
import {
  InvalidBackupCredentials,
  TooManyRequests,
  BackupConflict,
  PermissionDenied,
  NotAuthenticated,
} from "@/domain/exceptions"
import { ImportBackup } from "@/domain/usecases"
import {
  BackupRepository,
  BackupLocalRegistry,
  BackupProcessor,
  CloudRegister,
  Backupable,
  DatasourceInitiator,
} from "../ports"

const BACKUP_OPERATION_COOLDOWN_MINUTES = 5

export class ImportBackupImpl implements ImportBackup {
  constructor(
    private datasourceInitiator: DatasourceInitiator,
    private backupablePorts: Map<BackupFileType, Backupable>,
    private backupProcessor: BackupProcessor,
    private backupRepository: BackupRepository,
    private backupLocalRegistry: BackupLocalRegistry,
    private cloudRegister: CloudRegister,
  ) {}

  async execute(request: ImportBackupRequest): Promise<BackupSyncResult> {
    const auth = await this.cloudRegister.getAuth()

    if (!auth) {
      throw new NotAuthenticated()
    }

    if (!auth.permissions?.includes(CloudPermission.BACKUP_IMPORT)) {
      throw new PermissionDenied(CloudPermission.BACKUP_IMPORT)
    }

    await this.checkCooldown()

    const backupPassword = await this.datasourceInitiator.getHashedPassword()
    const bkgPass = backupPassword ?? request.password
    if (!bkgPass) {
      throw new InvalidBackupCredentials("NO_PASSWORD_PROVIDED")
    }

    const remoteBkgInfo = await this.backupRepository.getInfo({
      auth: auth,
    })
    const remoteBackupPieces = remoteBkgInfo.pieces
    const localBkgInfo = await this.backupLocalRegistry.getInfo()
    const localBackupRegistry = localBkgInfo.pieces

    const pieceTypesToImport = new Set<BackupFileType>()

    for (const [typeStr, piece] of Object.entries(remoteBackupPieces)) {
      const pieceType = typeStr as BackupFileType

      if (!request.types.includes(pieceType)) {
        continue
      }

      const backupable = this.backupablePorts.get(pieceType)
      if (!backupable) {
        continue
      }

      const localBackup = localBackupRegistry[pieceType] ?? null
      const localLastUpdate = await backupable.getLastUpdated()
      const hasLocalChanges =
        localBackup === null ||
        (localLastUpdate !== null &&
          localLastUpdate > new Date(localBackup.date))

      // Already synced with this exact backup
      if (localBackup !== null && piece.id === localBackup.id) {
        continue
      }

      const pieceDate = new Date(piece.date)
      const localBackupDate = localBackup ? new Date(localBackup.date) : null

      // Remote is same age or older than our local backup - nothing new to import
      if (localBackupDate !== null && pieceDate <= localBackupDate) {
        continue
      }

      // CONFLICT: Remote is newer, but we have local uncommitted changes
      if (hasLocalChanges && !request.force) {
        throw new BackupConflict(
          `Conflict detected for ${pieceType}: remote backup is newer but you have local changes. ` +
            "Upload your changes first or use force import to overwrite local data.",
        )
      }

      pieceTypesToImport.add(pieceType)
    }

    const downloadResult = await this.backupRepository.download({
      types: Array.from(pieceTypesToImport),
      auth: auth,
    })

    const importedBackupInfos: BackupInfo[] = []
    const affectedPieces: Record<BackupFileType, FullBackupInfo> = {} as any

    for (const piece of downloadResult.pieces) {
      const backupable = this.backupablePorts.get(piece.type)
      if (!backupable) continue

      const processResult = await this.backupProcessor.decompile({
        protocol: piece.protocol,
        password: bkgPass,
        payload: piece.payload,
      })

      await backupable.importData(processResult.payload)

      // Register the imported backup locally so we know we're in sync
      const backupInfo: BackupInfo = {
        id: piece.id,
        protocol: piece.protocol,
        date: piece.date,
        type: piece.type,
        size: piece.payload.length,
      }
      importedBackupInfos.push(backupInfo)

      // Get updated state after import
      affectedPieces[piece.type] = {
        local: backupInfo,
        remote: backupInfo,
        lastUpdate: piece.date,
        hasLocalChanges: false,
        status: SyncStatus.SYNC,
      }
    }

    if (importedBackupInfos.length > 0) {
      await this.backupLocalRegistry.insert(importedBackupInfos)
    }

    return { pieces: affectedPieces }
  }

  private async checkCooldown(): Promise<void> {
    const localBkgInfo = await this.backupLocalRegistry.getInfo()
    const localBackupRegistry = localBkgInfo.pieces

    if (Object.keys(localBackupRegistry).length === 0) {
      return
    }

    const now = new Date()
    const cooldownMs = BACKUP_OPERATION_COOLDOWN_MINUTES * 60 * 1000

    for (const backupInfo of Object.values(localBackupRegistry)) {
      if (!backupInfo) continue
      const backupDate = new Date(backupInfo.date)
      const timeSinceLastOperation = now.getTime() - backupDate.getTime()

      if (timeSinceLastOperation < cooldownMs) {
        const remainingSeconds = Math.ceil(
          (cooldownMs - timeSinceLastOperation) / 1000,
        )
        throw new TooManyRequests(
          `Please wait ${remainingSeconds} seconds before performing another backup operation`,
        )
      }
    }
  }
}
