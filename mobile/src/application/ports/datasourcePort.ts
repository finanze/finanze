export interface DatasourceInitiator {
  getHashedPassword(): Promise<string | null>
  initialize(password: string): Promise<void>
  exists(): Promise<boolean>
}
