export interface InitializeDatasource {
  execute(password: string): Promise<void>
}
