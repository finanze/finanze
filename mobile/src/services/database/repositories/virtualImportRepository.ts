import { DataManager } from "../dataManager"
import { Feature, VirtualDataImport, VirtualDataSource } from "@/domain"
import { VirtualImportRegistry } from "@/application/ports"
import { VirtualImportQueries } from "./queries"

function uuidV4(): string {
  const anyCrypto = globalThis as any
  if (anyCrypto?.crypto?.randomUUID) {
    return anyCrypto.crypto.randomUUID()
  }

  const bytes = Array.from({ length: 16 }, () =>
    Math.floor(Math.random() * 256),
  )
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = bytes.map(b => b.toString(16).padStart(2, "0")).join("")
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

function parseFeature(value: unknown): Feature | null {
  if (typeof value !== "string" || value.length === 0) return null
  // DB stores enum values like 'POSITION'
  if ((Object.values(Feature) as string[]).includes(value)) {
    return value as Feature
  }
  return null
}

export class VirtualImportRepository implements VirtualImportRegistry {
  constructor(private client: DataManager) {}

  async insert(entries: VirtualDataImport[]): Promise<void> {
    if (!entries || entries.length === 0) return

    await this.client.transaction(async () => {
      for (const entry of entries) {
        await this.client.execute(VirtualImportQueries.INSERT, [
          uuidV4(),
          entry.importId,
          entry.globalPositionId ?? null,
          entry.source,
          entry.date,
          entry.feature ?? null,
          entry.entityId ?? null,
        ])
      }
    })
  }

  async getLastImportRecords(
    source?: VirtualDataSource,
  ): Promise<VirtualDataImport[]> {
    const params: any[] = []
    let where = ""
    if (source) {
      where = " WHERE source = ? "
      params.push(source)
    }

    const query = VirtualImportQueries.GET_LAST_IMPORT_RECORDS_BASE.replace(
      "{where}",
      where,
    )

    try {
      const result = await this.client.query<any>(query, params)
      return result.rows.map(row => ({
        importId: row.import_id,
        globalPositionId: row.global_position_id ?? null,
        source: row.source as VirtualDataSource,
        date: row.date,
        feature: parseFeature(row.feature),
        entityId: row.entity_id ?? null,
      }))
    } catch {
      return []
    }
  }

  async deleteByImportAndFeature(
    importId: string,
    feature: Feature,
  ): Promise<void> {
    await this.client.execute(
      VirtualImportQueries.DELETE_BY_IMPORT_AND_FEATURE,
      [importId, feature],
    )
  }

  async deleteByImportFeatureAndEntity(
    importId: string,
    feature: Feature,
    entityId: string,
  ): Promise<void> {
    await this.client.execute(
      VirtualImportQueries.DELETE_BY_IMPORT_FEATURE_AND_ENTITY,
      [importId, feature, entityId],
    )
  }
}
