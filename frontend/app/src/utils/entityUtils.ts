import { EntityStatus, EntityType, type Entity } from "@/types"

const ACCOUNT_SCOPED_ENTITY_TYPES: readonly EntityType[] = [
  EntityType.CRYPTO_EXCHANGE,
  EntityType.MARKET_FORECAST_PLATFORM,
]

export const isAccountScopedEntity = (entityType: EntityType): boolean =>
  ACCOUNT_SCOPED_ENTITY_TYPES.includes(entityType)

export const getConnectedAccountIds = (entity: Entity): string[] =>
  isAccountScopedEntity(entity.type)
    ? (entity.accounts ?? [])
        .filter(account => account.status === EntityStatus.CONNECTED)
        .map(account => account.id)
    : []
