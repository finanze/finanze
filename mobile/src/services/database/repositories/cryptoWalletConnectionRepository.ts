import { DataManager } from "../dataManager"
import { CryptoWalletConnection } from "@/domain"
import { CryptoWalletConnectionPort } from "@/application/ports"
import { CryptoWalletConnectionQueries } from "./queries"

export class CryptoWalletConnectionRepository implements CryptoWalletConnectionPort {
  constructor(private client: DataManager) {}

  async getByEntityId(entityId: string): Promise<CryptoWalletConnection[]> {
    try {
      const result = await this.client.query<any>(
        CryptoWalletConnectionQueries.GET_BY_ENTITY_ID,
        [entityId],
      )

      return result.rows.map(row => ({
        id: row.id,
        entityId: row.entity_id,
        address: row.address,
        name: row.name,
      }))
    } catch {
      return []
    }
  }

  async getByEntityAndAddress(
    entityId: string,
    address: string,
  ): Promise<CryptoWalletConnection | null> {
    try {
      const result = await this.client.query<any>(
        CryptoWalletConnectionQueries.GET_BY_ENTITY_AND_ADDRESS,
        [entityId, address],
      )
      if (result.rows.length === 0) return null
      const row = result.rows[0]
      return {
        id: row.id,
        entityId: row.entity_id,
        address: row.address,
        name: row.name,
      }
    } catch {
      return null
    }
  }

  async getConnectedEntities(): Promise<string> {
    try {
      const result = await this.client.query<any>(
        CryptoWalletConnectionQueries.GET_CONNECTED_ENTITIES,
      )
      const ids = result.rows.map((r: any) => r.entity_id)
      return ids.join(",")
    } catch {
      return ""
    }
  }

  async insert(connection: CryptoWalletConnection): Promise<void> {
    await this.client.execute(CryptoWalletConnectionQueries.INSERT, [
      connection.id,
      connection.entityId,
      connection.address,
      connection.name,
      new Date().toISOString(),
    ])
  }

  async rename(walletConnectionId: string, name: string): Promise<void> {
    await this.client.execute(CryptoWalletConnectionQueries.RENAME, [
      name,
      walletConnectionId,
    ])
  }

  async delete(walletConnectionId: string): Promise<void> {
    await this.client.execute(CryptoWalletConnectionQueries.DELETE, [
      walletConnectionId,
    ])
  }
}
