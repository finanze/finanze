import { PendingFlow } from "@/domain"
import { PendingFlowPort } from "@/application/ports"
import { GetPendingFlows } from "@/domain/usecases"

export class GetPendingFlowsImpl implements GetPendingFlows {
  constructor(private pendingFlowPort: PendingFlowPort) {}

  async execute(): Promise<PendingFlow[]> {
    return this.pendingFlowPort.getAll()
  }
}
