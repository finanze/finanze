import { BackupProcessRequest, BackupProcessResult } from "@/domain"

export interface BackupProcessor {
  decompile(data: BackupProcessRequest): Promise<BackupProcessResult>
  compile(data: BackupProcessRequest): Promise<BackupProcessResult>
}
