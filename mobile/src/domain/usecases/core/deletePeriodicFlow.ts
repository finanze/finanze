export interface DeletePeriodicFlow {
  execute(flowId: string): Promise<void>
}
