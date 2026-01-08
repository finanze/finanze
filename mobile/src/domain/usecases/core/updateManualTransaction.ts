import { BaseTx } from "@/domain"

export interface UpdateManualTransaction {
  execute(tx: BaseTx): Promise<void>
}
