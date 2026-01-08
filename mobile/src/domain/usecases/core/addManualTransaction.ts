import { BaseTx } from "@/domain"

export interface AddManualTransaction {
  execute(tx: BaseTx): Promise<string>
}
