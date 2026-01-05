import { Backupable } from "../ports"
import type { GetLocalLastUpdate } from "@/domain/usecases"

export class GetLocalLastUpdateImpl implements GetLocalLastUpdate {
  constructor(private dataBackupable: Backupable) {}

  async execute(): Promise<Date | null> {
    return await this.dataBackupable.getLastUpdated()
  }
}
