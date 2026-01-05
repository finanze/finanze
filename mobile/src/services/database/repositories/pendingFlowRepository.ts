import { DataManager } from "../dataManager"
import { PendingFlow, FlowType } from "@/domain"
import { parseDezimalValue } from "@/domain"
import { PendingFlowPort } from "@/application/ports"
import { PendingFlowsQueries } from "./queries"

function uuidV4(): string {
  // Prefer native implementation if available
  const anyCrypto = globalThis as any
  if (anyCrypto?.crypto?.randomUUID) {
    return anyCrypto.crypto.randomUUID()
  }

  // Fallback RFC4122-ish v4
  const bytes = Array.from({ length: 16 }, () =>
    Math.floor(Math.random() * 256),
  )
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = bytes.map(b => b.toString(16).padStart(2, "0")).join("")
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

export class PendingFlowRepository implements PendingFlowPort {
  constructor(private client: DataManager) {}

  private async tableExists(name: string): Promise<boolean> {
    const res = await this.client.query<{ name: string }>(
      "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
      [name],
    )
    return res.rows.length > 0
  }

  async save(flows: PendingFlow[]): Promise<void> {
    const hasTable = await this.tableExists("pending_flows")
    if (!hasTable) return

    await this.client.transaction(async () => {
      for (const flow of flows) {
        const id = flow.id ?? uuidV4()
        await this.client.execute(PendingFlowsQueries.INSERT, [
          id,
          flow.name,
          String(flow.amount),
          flow.currency,
          flow.flowType,
          flow.category ?? null,
          flow.enabled ? 1 : 0,
          flow.date ?? null,
          flow.icon ?? null,
        ])
        flow.id = id
      }
    })
  }

  async deleteAll(): Promise<void> {
    const hasTable = await this.tableExists("pending_flows")
    if (!hasTable) return
    await this.client.execute(PendingFlowsQueries.DELETE_ALL)
  }

  async getAll(): Promise<PendingFlow[]> {
    const hasTable = await this.tableExists("pending_flows")
    if (!hasTable) return []

    const res = await this.client.query<any>(PendingFlowsQueries.GET_ALL)
    return res.rows.map((row: any) => ({
      id: row.id,
      name: row.name,
      amount: parseDezimalValue(row.amount),
      currency: row.currency,
      flowType: (row.flow_type as FlowType) || FlowType.EXPENSE,
      category: row.category ?? null,
      enabled: !!row.enabled,
      date: row.date ?? null,
      icon: row.icon ?? null,
    }))
  }
}
