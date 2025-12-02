import {
  Entity,
  EntityOrigin,
  EntitySessionCategory,
  EntityStatus,
  EntityType,
  AutoRefreshMaxOutdatedTime,
  FetchResultCode,
} from "@/types"

export const SESSION_CATEGORY_PRIORITY: Record<EntitySessionCategory, number> =
  {
    [EntitySessionCategory.NONE]: 0,
    [EntitySessionCategory.SHORT]: 1,
    [EntitySessionCategory.MEDIUM]: 2,
    [EntitySessionCategory.UNDEFINED]: 3,
  }

export const MIN_AUTO_REFRESH_SESSION_PRIORITY =
  SESSION_CATEGORY_PRIORITY[EntitySessionCategory.MEDIUM]

export function isCryptoWalletConnected(entity: Entity): boolean {
  return (
    entity.type === EntityType.CRYPTO_WALLET &&
    !!entity.connected &&
    entity.connected.length > 0
  )
}

export function isEntityConnected(entity: Entity): boolean {
  if (entity.type === EntityType.CRYPTO_WALLET) {
    return isCryptoWalletConnected(entity)
  }
  return entity.status === EntityStatus.CONNECTED
}

export function hasCompatibleSessionCategory(entity: Entity): boolean {
  if (!entity.session_category) return true
  const priority = SESSION_CATEGORY_PRIORITY[entity.session_category]
  return priority >= MIN_AUTO_REFRESH_SESSION_PRIORITY
}

export function isAutoRefreshCompatibleEntity(entity: Entity): boolean {
  const hasCompatibleOrigin =
    entity.origin === EntityOrigin.NATIVE ||
    entity.origin === EntityOrigin.EXTERNALLY_PROVIDED
  const hasValidSession = hasCompatibleSessionCategory(entity)
  const connected = isEntityConnected(entity)

  return hasCompatibleOrigin && hasValidSession && connected
}

export function getAutoRefreshCompatibleEntities(entities: Entity[]): Entity[] {
  return entities.filter(isAutoRefreshCompatibleEntity)
}

export function entityHasPin(entity: Entity): boolean {
  return !!entity.pin
}

export const MAX_OUTDATED_TIME_MS: Record<AutoRefreshMaxOutdatedTime, number> =
  {
    [AutoRefreshMaxOutdatedTime.THREE_HOURS]: 3 * 60 * 60 * 1000,
    [AutoRefreshMaxOutdatedTime.SIX_HOURS]: 6 * 60 * 60 * 1000,
    [AutoRefreshMaxOutdatedTime.TWELVE_HOURS]: 12 * 60 * 60 * 1000,
    [AutoRefreshMaxOutdatedTime.DAY]: 24 * 60 * 60 * 1000,
    [AutoRefreshMaxOutdatedTime.TWO_DAYS]: 2 * 24 * 60 * 60 * 1000,
    [AutoRefreshMaxOutdatedTime.WEEK]: 7 * 24 * 60 * 60 * 1000,
  }

export const RETRIABLE_FETCH_CODES: FetchResultCode[] = [
  FetchResultCode.PARTIALLY_COMPLETED,
  FetchResultCode.COOLDOWN,
  FetchResultCode.REMOTE_FAILED,
  FetchResultCode.UNEXPECTED_LOGIN_ERROR,
]

export const MAX_AUTO_REFRESH_RETRIES = 3
