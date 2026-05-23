import {
  type Entity,
  type Feature,
  EntityType,
  EntityOrigin,
  EntityStatus,
  EntitySessionCategory,
  AutoRefreshMode,
  AutoRefreshMaxOutdatedTime,
  type AutoRefreshEntityEntry,
} from "@/types"
import type { AutoRefreshCandidate } from "@/services/autoRefreshService"

let entityCounter = 0

export function buildEntity(overrides: Partial<Entity> = {}): Entity {
  entityCounter++
  const id = overrides.id ?? `entity-${entityCounter}`
  return {
    id,
    name: overrides.name ?? `Entity ${entityCounter}`,
    type: EntityType.FINANCIAL_INSTITUTION,
    origin: EntityOrigin.NATIVE,
    natural_id: `nat-${id}`,
    status: EntityStatus.CONNECTED,
    features: ["POSITION"] as Feature[],
    last_fetch: {} as Record<Feature, string>,
    virtual_features: {} as Record<Feature, string>,
    fetchable: true,
    session_category: EntitySessionCategory.MEDIUM,
    ...overrides,
  }
}

export function buildCandidate(
  entityOverrides: Partial<Entity> = {},
  features?: Feature[],
): AutoRefreshCandidate {
  const entity = buildEntity(entityOverrides)
  return {
    entity,
    features: features ?? entity.features,
  }
}

export function buildAutoRefreshSettings(
  overrides: Partial<{
    mode: AutoRefreshMode
    max_outdated: AutoRefreshMaxOutdatedTime
    entities: AutoRefreshEntityEntry[]
  }> = {},
) {
  return {
    mode: AutoRefreshMode.NO_2FA,
    max_outdated: AutoRefreshMaxOutdatedTime.TWELVE_HOURS,
    entities: [] as AutoRefreshEntityEntry[],
    ...overrides,
  }
}

export function resetBuilderCounters() {
  entityCounter = 0
}
