import type React from "react"
import { motion, AnimatePresence } from "framer-motion"

import { useState, useMemo, useEffect } from "react"
import { Button } from "@/components/ui/Button"
import { useAppContext } from "@/context/AppContext"
import { useEntityWorkflow } from "@/context/EntityWorkflowContext"
import { useI18n } from "@/i18n"
import { Entity, EntityOrigin, EntityStatus, EntityType } from "@/types"
import {
  Database,
  RefreshCw,
  History,
  ChevronDown,
  AlertCircle,
} from "lucide-react"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { formatTimeAgoAbbr } from "@/lib/timeUtils"
import { getImageUrl } from "@/services/api"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import {
  getAutoRefreshEntityState,
  requiresUserAction,
} from "@/services/autoRefreshService"
import { isAutoRefreshCompatibleEntity } from "@/utils/autoRefreshUtils"

export function EntityRefreshDropdown() {
  const { entities } = useAppContext()
  const { scrape, fetchingEntityState, setFetchingEntityState } =
    useEntityWorkflow()
  const { t } = useI18n()
  const [isOpen, setIsOpen] = useState(false)
  const [entityImages, setEntityImages] = useState<Record<string, string>>({})
  const [refreshCooldown, setRefreshCooldown] = useState(false)

  const { fetchingEntityIds } = fetchingEntityState

  const connectedEntities = useMemo(
    () =>
      entities?.filter(
        entity =>
          entity.status !== EntityStatus.DISCONNECTED &&
          entity.origin !== "MANUAL",
      ) || [],
    [entities],
  )

  // Separate financial institutions and crypto wallets
  const financialEntities = connectedEntities.filter(
    entity => entity.type === EntityType.FINANCIAL_INSTITUTION,
  )
  // Only include crypto entities that have connected wallets
  const cryptoEntities = connectedEntities.filter(
    entity =>
      entity.type === EntityType.CRYPTO_WALLET &&
      entity.connected &&
      entity.connected.length > 0,
  )

  // Check if any crypto entities are being fetched
  const isCryptoFetching = cryptoEntities.some(entity =>
    fetchingEntityIds.includes(entity.id),
  )

  useEffect(() => {
    const loadImages = async () => {
      const images: Record<string, string> = {}
      for (const entity of connectedEntities) {
        try {
          if (entity.origin === EntityOrigin.EXTERNALLY_PROVIDED) {
            if (entity.icon_url) {
              images[entity.id] = entity.icon_url
            } else {
              images[entity.id] = await getImageUrl(
                `/static/entities/logos/${entity.id}.png`,
              )
            }
          } else {
            images[entity.id] = `entities/${entity.id}.png`
          }
        } catch {
          images[entity.id] = `entities/${entity.id}.png`
        }
      }
      setEntityImages(images)
    }
    loadImages()
  }, [connectedEntities])

  const handleRefreshEntity = async (entity: Entity, e: React.MouseEvent) => {
    e.stopPropagation()

    if (!entity || refreshCooldown) return

    setRefreshCooldown(true)
    setTimeout(() => setRefreshCooldown(false), 700)

    try {
      setFetchingEntityState(prev => ({
        ...prev,
        fetchingEntityIds: [...prev.fetchingEntityIds, entity.id],
      }))

      const features = entity.features || []
      const avoidNewLogin = false
      const options = { avoidNewLogin }
      await scrape(entity, features, options)
    } finally {
      setFetchingEntityState(prev => ({
        ...prev,
        fetchingEntityIds: prev.fetchingEntityIds.filter(
          id => id !== entity.id,
        ),
      }))
    }
  }

  const handleRefreshCrypto = async (e: React.MouseEvent) => {
    e.stopPropagation()

    if (cryptoEntities.length === 0 || refreshCooldown) return

    setRefreshCooldown(true)
    setTimeout(() => setRefreshCooldown(false), 700)

    try {
      // Add all connected crypto entities to fetchingEntityIds
      setFetchingEntityState(prev => ({
        ...prev,
        fetchingEntityIds: [
          ...prev.fetchingEntityIds,
          ...cryptoEntities.map(entity => entity.id),
        ],
      }))

      // Get all unique features from crypto entities
      const allFeatures = [
        ...new Set(cryptoEntities.flatMap(entity => entity.features || [])),
      ]
      const options = { avoidNewLogin: true }
      // Pass null as entity to scrape all crypto entities
      await scrape(null, allFeatures, options)
    } finally {
      // Remove all crypto entities from fetchingEntityIds
      setFetchingEntityState(prev => ({
        ...prev,
        fetchingEntityIds: prev.fetchingEntityIds.filter(
          id => !cryptoEntities.some(entity => entity.id === id),
        ),
      }))
    }
  }

  const isUpdateOld = (date: Date | null): boolean => {
    if (!date) return false
    const now = new Date()
    const diffTime = now.getTime() - date.getTime()
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24))
    return diffDays > 7
  }

  const getEntityLastFetchDate = (entity: Entity): Date | null => {
    if (!entity.last_fetch) return null

    const fetchDates = Object.values(entity.last_fetch)
      .filter(dateStr => dateStr && dateStr.trim() !== "")
      .map(dateStr => new Date(dateStr))
      .filter(date => !isNaN(date.getTime()))

    return fetchDates.length > 0
      ? new Date(Math.max(...fetchDates.map(date => date.getTime())))
      : null
  }

  const entityRequiresLogin = (entity: Entity): boolean => {
    if (!isAutoRefreshCompatibleEntity(entity)) return false
    const state = getAutoRefreshEntityState(entity.id)
    return state ? requiresUserAction(state) : false
  }

  const entitiesWithLastUpdate = useMemo(() => {
    if (!connectedEntities) {
      return []
    }

    const result = []

    // Add individual financial entities
    const financialEntitiesWithUpdate = financialEntities
      .map(entity => {
        const lastUpdatedAt = getEntityLastFetchDate(entity)
        return { type: "entity" as const, entity, lastUpdatedAt }
      })
      .sort((a, b) => {
        if (a.lastUpdatedAt && b.lastUpdatedAt) {
          return b.lastUpdatedAt.getTime() - a.lastUpdatedAt.getTime()
        }
        if (a.lastUpdatedAt) return -1
        if (b.lastUpdatedAt) return 1
        return a.entity.name.localeCompare(b.entity.name)
      })

    result.push(...financialEntitiesWithUpdate)

    // Add crypto group if there are crypto entities
    if (cryptoEntities.length > 0) {
      // Find the most recent update among all crypto entities
      const cryptoLastUpdates = cryptoEntities
        .map(entity => getEntityLastFetchDate(entity))
        .filter(Boolean)

      const lastCryptoUpdate =
        cryptoLastUpdates.length > 0
          ? new Date(
              Math.max(...cryptoLastUpdates.map(date => date!.getTime())),
            )
          : null

      result.push({
        type: "crypto" as const,
        entity: null,
        lastUpdatedAt: lastCryptoUpdate,
        cryptoEntities,
      })
    }

    // Sort the entire result by last updated date
    return result.sort((a, b) => {
      if (a.lastUpdatedAt && b.lastUpdatedAt) {
        return b.lastUpdatedAt.getTime() - a.lastUpdatedAt.getTime()
      }
      if (a.lastUpdatedAt) return -1
      if (b.lastUpdatedAt) return 1
      // If both don't have dates, sort entities before crypto
      if (a.type === "entity" && b.type === "crypto") return -1
      if (a.type === "crypto" && b.type === "entity") return 1
      return 0
    })
  }, [connectedEntities, financialEntities, cryptoEntities])

  if (entitiesWithLastUpdate.length === 0) {
    return null
  }

  return (
    <div className="relative">
      <Button
        variant="outline"
        className="flex items-center gap-1 h-9 px-3 text-sm"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        aria-haspopup="true"
      >
        {fetchingEntityIds.length > 0 ? (
          <LoadingSpinner size="sm" />
        ) : (
          <Database className="h-4 w-4" />
        )}
        {t.dashboard.data}
        <ChevronDown className="h-4 w-4" />
      </Button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2, ease: "easeInOut" }}
            className="absolute right-0 mt-2 w-72 rounded-md shadow-md bg-popover z-50 border"
          >
            <div className="py-1" role="menu" aria-orientation="vertical">
              <div className="px-4 py-3 text-sm font-medium flex items-center">
                <History className="h-4 w-4 mr-2" />
                {t.entities.refreshEntity}
              </div>
              <div className="max-h-80 overflow-y-auto">
                {entitiesWithLastUpdate.map(item => {
                  if (item.type === "entity") {
                    const { entity, lastUpdatedAt } = item
                    return (
                      <div
                        key={entity.id}
                        className="pl-3 pr-4 py-1.5 text-sm flex items-center justify-between hover:bg-neutral-100 dark:hover:bg-neutral-800"
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <div className="h-5 w-5 flex-shrink-0 overflow-hidden rounded">
                            <img
                              src={entityImages[entity.id]}
                              alt={entity.name}
                              className="h-full w-full object-contain"
                              onError={e =>
                                (e.currentTarget.src =
                                  "entities/entity_placeholder.png")
                              }
                            />
                          </div>
                          <div className="min-w-0">
                            <span className="truncate block">
                              {entity.name}
                            </span>
                            {lastUpdatedAt ? (
                              <p
                                className={`text-xs mt-0.5 ${
                                  isUpdateOld(lastUpdatedAt)
                                    ? "text-orange-300"
                                    : "text-neutral-400"
                                }`}
                              >
                                {formatTimeAgoAbbr(lastUpdatedAt, t)}
                              </p>
                            ) : (
                              <p className="text-xs mt-0.5 text-neutral-500">
                                {t.common.never}
                              </p>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-1">
                          {entityRequiresLogin(entity) && (
                            <Popover>
                              <PopoverTrigger asChild>
                                <button
                                  type="button"
                                  className="p-1.5 text-amber-500 hover:text-amber-400 transition-colors"
                                  onClick={e => e.stopPropagation()}
                                >
                                  <AlertCircle className="h-4 w-4" />
                                </button>
                              </PopoverTrigger>
                              <PopoverContent
                                className="w-56 p-2 text-xs"
                                side="left"
                                align="center"
                              >
                                {t.entities.sessionExpiredHint}
                              </PopoverContent>
                            </Popover>
                          )}
                          {entity.fetchable &&
                            (fetchingEntityIds.includes(entity.id) ? (
                              <div className="p-1.5">
                                <LoadingSpinner size="sm" className="p-1.5" />
                              </div>
                            ) : (
                              <button
                                onClick={e => handleRefreshEntity(entity, e)}
                                disabled={refreshCooldown}
                                className={`p-1.5 rounded-full transition-all duration-200 ${refreshCooldown ? "opacity-40 cursor-not-allowed" : "hover:bg-gray-200 dark:hover:bg-gray-700"}`}
                                aria-label={`Refresh ${entity.name}`}
                              >
                                <RefreshCw className="h-4 w-4" />
                              </button>
                            ))}
                        </div>
                      </div>
                    )
                  } else {
                    // Crypto group
                    const { lastUpdatedAt, cryptoEntities: cryptoItems } = item

                    // Format crypto entities display - only show entities with connected wallets
                    const activeCryptoEntities = cryptoItems.filter(
                      entity => entity.connected && entity.connected.length > 0,
                    )

                    const cryptoDisplay =
                      activeCryptoEntities.length <= 2
                        ? activeCryptoEntities.map(e => e.name).join(", ")
                        : `${activeCryptoEntities[0].name}, +${activeCryptoEntities.length - 1}`

                    return (
                      <div
                        key="crypto-group"
                        className="pl-3 pr-4 py-1.5 text-sm flex items-center justify-between hover:bg-neutral-100 dark:hover:bg-neutral-800"
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <div className="flex -space-x-2 flex-shrink-0 w-5">
                            {activeCryptoEntities
                              .slice(0, 3)
                              .map(cryptoEntity => (
                                <div
                                  key={cryptoEntity.id}
                                  className="h-5 w-5 overflow-hidden rounded"
                                >
                                  <img
                                    src={entityImages[cryptoEntity.id]}
                                    alt={cryptoEntity.name}
                                    className="h-full w-full object-contain"
                                    onError={e =>
                                      (e.currentTarget.src =
                                        "entities/entity_placeholder.png")
                                    }
                                  />
                                </div>
                              ))}
                          </div>
                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              <span>{t.common.crypto}</span>
                              <span className="text-xs text-neutral-500 truncate">
                                {cryptoDisplay}
                              </span>
                            </div>
                            {lastUpdatedAt ? (
                              <p
                                className={`text-xs mt-0.5 ${
                                  isUpdateOld(lastUpdatedAt)
                                    ? "text-orange-300"
                                    : "text-neutral-400"
                                }`}
                              >
                                {formatTimeAgoAbbr(lastUpdatedAt, t)}
                              </p>
                            ) : (
                              <p className="text-xs mt-0.5 text-neutral-500">
                                {t.common.never}
                              </p>
                            )}
                          </div>
                        </div>
                        {isCryptoFetching ? (
                          <div className="p-1.5">
                            <LoadingSpinner size="sm" className="p-1.5" />
                          </div>
                        ) : (
                          <button
                            onClick={handleRefreshCrypto}
                            disabled={refreshCooldown}
                            className={`p-1.5 rounded-full transition-all duration-200 ${refreshCooldown ? "opacity-40 cursor-not-allowed" : "hover:bg-gray-200 dark:hover:bg-gray-700"}`}
                            aria-label={`Refresh ${t.common.crypto}`}
                          >
                            <RefreshCw className="h-4 w-4" />
                          </button>
                        )}
                      </div>
                    )
                  }
                })}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {isOpen && (
        <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} />
      )}
    </div>
  )
}
