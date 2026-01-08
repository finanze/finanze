import { Feature } from "./entity"

export enum VirtualDataSource {
  SHEETS = "SHEETS",
  MANUAL = "MANUAL",
}

export interface VirtualDataImport {
  importId: string
  globalPositionId: string | null
  source: VirtualDataSource
  date: string
  feature: Feature | null
  entityId: string | null
}
