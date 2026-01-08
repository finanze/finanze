import { Feature, VirtualDataImport, VirtualDataSource } from "@/domain"

export interface VirtualImportRegistry {
  insert(entries: VirtualDataImport[]): Promise<void>
  getLastImportRecords(
    source?: VirtualDataSource | null,
  ): Promise<VirtualDataImport[]>
  deleteByImportAndFeature(importId: string, feature: Feature): Promise<void>
  deleteByImportFeatureAndEntity(
    importId: string,
    feature: Feature,
    entityId: string,
  ): Promise<void>
}
