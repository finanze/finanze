import { ExternalEntity, ExternalEntityStatus } from "@/domain"

export interface ExternalEntityPort {
  upsert(ee: ExternalEntity): Promise<void>
  updateStatus(eeId: string, status: ExternalEntityStatus): Promise<void>
  getById(eeId: string): Promise<ExternalEntity | null>
  getByEntityId(entityId: string): Promise<ExternalEntity | null>
  deleteById(eeId: string): Promise<void>
  getAll(): Promise<ExternalEntity[]>
}
