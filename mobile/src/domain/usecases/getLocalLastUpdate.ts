export interface GetLocalLastUpdate {
  execute(): Promise<Date | null>
}
