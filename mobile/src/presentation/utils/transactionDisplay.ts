import { TxType } from "@/domain"

export type TransactionDisplayType = "in" | "out"

// Keep this mapping in sync with the web app's `getTransactionDisplayType`.
// Outgoing transactions are generally neutral in UI (no sign), except fees.
const OUTGOING_TYPES: ReadonlySet<TxType> = new Set([
  TxType.BUY,
  TxType.INVESTMENT,
  TxType.SUBSCRIPTION,
  TxType.SWAP_FROM,
  TxType.SWAP_TO,
  TxType.TRANSFER_OUT,
  TxType.SWITCH_FROM,
  TxType.SWITCH_TO,
  TxType.TRANSFER_IN,
  TxType.FEE,
])

export function getTransactionDisplayType(
  type: TxType,
): TransactionDisplayType {
  return OUTGOING_TYPES.has(type) ? "out" : "in"
}
