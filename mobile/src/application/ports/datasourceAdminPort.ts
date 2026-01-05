export interface DatasourceAdminPort {
  deleteDatabase(): Promise<void>
}
