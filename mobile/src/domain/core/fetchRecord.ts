import { Feature } from "./entity"

export interface FetchRecord {
  entityId: string
  feature: Feature
  date: string
}

export enum DataSource {
  SHEETS = "SHEETS",
  MANUAL = "MANUAL",
  REAL = "REAL",
}
