import { BackupLocalRegistry, DatasourceAdminPort } from "../ports"
import type { ClearLocalData } from "@/domain/usecases"

export class ClearLocalDataImpl implements ClearLocalData {
  constructor(
    private datasourceAdmin: DatasourceAdminPort,
    private backupLocalRegistry: BackupLocalRegistry,
  ) {}

  async execute(): Promise<void> {
    await this.datasourceAdmin.deleteDatabase()
    await this.backupLocalRegistry.clear()
  }
}
