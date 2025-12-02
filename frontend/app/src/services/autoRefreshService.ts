import {
  Entity,
  AutoRefreshMaxOutdatedTime,
  FetchResultCode,
  FetchResponse,
  Feature,
  AutoRefreshEntityEntry,
} from "@/types"
import {
  getAutoRefreshCompatibleEntities,
  MAX_OUTDATED_TIME_MS,
  RETRIABLE_FETCH_CODES,
  MAX_AUTO_REFRESH_RETRIES,
} from "@/utils/autoRefreshUtils"

const AUTO_REFRESH_STATE_KEY = "autoRefreshState"

export interface AutoRefreshEntityState {
  lastAttempt: string
  retryCount: number
  lastCode?: FetchResultCode
  lastDetails?: Record<string, unknown>
  httpStatusCode?: number
}

interface AutoRefreshStorageState {
  entities: Record<string, AutoRefreshEntityState>
}

function getStoredState(): AutoRefreshStorageState {
  try {
    const stored = localStorage.getItem(AUTO_REFRESH_STATE_KEY)
    if (stored) {
      return JSON.parse(stored)
    }
  } catch {
    // Ignore parse errors
  }
  return { entities: {} }
}

function saveState(state: AutoRefreshStorageState): void {
  try {
    localStorage.setItem(AUTO_REFRESH_STATE_KEY, JSON.stringify(state))
  } catch {
    // Ignore storage errors
  }
}

export function getAutoRefreshEntityState(
  entityId: string,
): AutoRefreshEntityState | null {
  const state = getStoredState()
  return state.entities[entityId] || null
}

function updateEntityState(
  entityId: string,
  update: Partial<AutoRefreshEntityState>,
): void {
  const state = getStoredState()
  const existing = state.entities[entityId] || {
    lastAttempt: new Date().toISOString(),
    retryCount: 0,
  }
  state.entities[entityId] = { ...existing, ...update }
  saveState(state)
}

function clearEntityRetryState(entityId: string): void {
  const state = getStoredState()
  if (state.entities[entityId]) {
    delete state.entities[entityId]
    saveState(state)
  }
}

export function requiresUserAction(
  entityState: AutoRefreshEntityState,
): boolean {
  return (
    entityState.lastCode === FetchResultCode.LOGIN_REQUIRED ||
    entityState.lastCode === FetchResultCode.NOT_LOGGED ||
    entityState.lastCode === FetchResultCode.LINK_EXPIRED ||
    entityState.lastCode === FetchResultCode.MANUAL_LOGIN
  )
}

function isRetriableFailure(entityState: AutoRefreshEntityState): boolean {
  if (entityState.httpStatusCode) {
    return true
  }

  if (
    entityState.lastCode &&
    RETRIABLE_FETCH_CODES.includes(entityState.lastCode)
  ) {
    return true
  }

  return false
}

function getEntityLastFetchTime(entity: Entity): Date | null {
  if (!entity.last_fetch) return null

  const fetchDates = Object.values(entity.last_fetch)
    .filter(dateStr => dateStr && dateStr.trim() !== "")
    .map(dateStr => new Date(dateStr))
    .filter(date => !isNaN(date.getTime()))

  return fetchDates.length > 0
    ? new Date(Math.max(...fetchDates.map(date => date.getTime())))
    : null
}

function shouldAutoRefreshEntity(
  entity: Entity,
  maxOutdatedTime: AutoRefreshMaxOutdatedTime,
): boolean {
  const maxOutdatedMs = MAX_OUTDATED_TIME_MS[maxOutdatedTime]
  const now = Date.now()

  const lastFetchTime = getEntityLastFetchTime(entity)
  const lastFetchMs = lastFetchTime?.getTime() || 0

  const entityState = getAutoRefreshEntityState(entity.id)

  if (entityState) {
    // If user action is required (login expired, manual login needed, etc.)
    // don't auto-refresh - user must manually re-login first
    if (requiresUserAction(entityState)) {
      return false
    }

    const lastAttemptMs = new Date(entityState.lastAttempt).getTime()

    if (entityState.retryCount >= MAX_AUTO_REFRESH_RETRIES) {
      // Max retries reached, stop auto-refresh attempts
      return false
    }

    if (isRetriableFailure(entityState)) {
      // For retriable failures, wait maxOutdatedTime since the last attempt
      return now - lastAttemptMs >= maxOutdatedMs
    }
  }

  if (!lastFetchTime) {
    return true
  }

  return now - lastFetchMs >= maxOutdatedMs
}

export interface AutoRefreshCandidate {
  entity: Entity
  features: Feature[]
}

export function getAutoRefreshCandidates(
  entities: Entity[],
  maxOutdatedTime: AutoRefreshMaxOutdatedTime,
  selectedEntities: AutoRefreshEntityEntry[],
): AutoRefreshCandidate[] {
  const compatibleEntities = getAutoRefreshCompatibleEntities(entities)

  const selectedEntityIds = selectedEntities.map(e => e.id)

  let candidatePool: Entity[]
  if (selectedEntityIds.length === 0) {
    candidatePool = compatibleEntities
  } else {
    candidatePool = compatibleEntities.filter(entity =>
      selectedEntityIds.includes(entity.id),
    )
  }

  return candidatePool
    .filter(entity => shouldAutoRefreshEntity(entity, maxOutdatedTime))
    .map(entity => ({
      entity,
      features: entity.features || [],
    }))
}

export function recordAutoRefreshSuccess(entityId: string): void {
  clearEntityRetryState(entityId)
}

export function recordAutoRefreshFailure(
  entityId: string,
  response?: FetchResponse,
  httpStatusCode?: number,
): void {
  const existingState = getAutoRefreshEntityState(entityId)
  const currentRetryCount = existingState?.retryCount || 0

  updateEntityState(entityId, {
    lastAttempt: new Date().toISOString(),
    retryCount: currentRetryCount + 1,
    lastCode: response?.code,
    lastDetails: response?.details as Record<string, unknown> | undefined,
    httpStatusCode,
  })
}

export function resetAutoRefreshState(): void {
  try {
    localStorage.removeItem(AUTO_REFRESH_STATE_KEY)
  } catch {
    // Ignore
  }
}
