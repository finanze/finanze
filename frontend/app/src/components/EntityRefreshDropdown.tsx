import type React from "react"
import { motion, AnimatePresence } from "framer-motion"

import { useState, useMemo } from "react"
import { Button } from "@/components/ui/Button"
import { useAppContext } from "@/context/AppContext"
import { useI18n } from "@/i18n"
import { Entity, EntityStatus, EntityType } from "@/types"
import { Database, RefreshCw, History, ChevronDown } from "lucide-react"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { formatTimeAgo } from "@/lib/timeUtils"

export function EntityRefreshDropdown() {
  const { entities, scrape, fetchingEntityState, setFetchingEntityState } =
    useAppContext()
  const { t } = useI18n()
  const [isOpen, setIsOpen] = useState(false)

  const { fetchingEntityIds } = fetchingEntityState

  const connectedEntities =
    entities?.filter(
      entity => entity.status !== EntityStatus.DISCONNECTED && entity.is_real,
    ) || []

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

  const handleRefreshEntity = async (entity: Entity, e: React.MouseEvent) => {
    e.stopPropagation()

    if (!entity) return

    try {
      setFetchingEntityState(prev => ({
        ...prev,
        fetchingEntityIds: [...prev.fetchingEntityIds, entity.id],
      }))

      const features = entity.features || []
      const options = { avoidNewLogin: true }
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

    if (cryptoEntities.length === 0) return

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
        className="flex items-center gap-1"
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
            className="absolute right-0 mt-2 w-72 rounded-md shadow-lg bg-neutral-950/80 backdrop-blur-md border border-neutral-700/50 z-50"
          >
            <div className="py-1" role="menu" aria-orientation="vertical">
              <div className="px-4 py-3 text-sm font-medium text-neutral-400 border-b border-neutral-700/50 flex items-center">
                <History className="h-4 w-4 mr-2 text-neutral-500" />
                {t.entities.refreshEntity}
              </div>
              <div className="max-h-80 overflow-y-auto">
                {entitiesWithLastUpdate.map(item => {
                  if (item.type === "entity") {
                    const { entity, lastUpdatedAt } = item
                    return (
                      <div
                        key={entity.id}
                        className="px-4 py-1.5 text-sm text-neutral-100 flex items-center justify-between hover:bg-neutral-800/50 border-b border-neutral-700/60 last:border-b-0"
                      >
                        <div>
                          <span>{entity.name}</span>
                          {lastUpdatedAt ? (
                            <p
                              className={`text-xs mt-0.5 ${
                                isUpdateOld(lastUpdatedAt)
                                  ? "text-orange-300"
                                  : "text-neutral-400"
                              }`}
                            >
                              {formatTimeAgo(lastUpdatedAt, t)}
                            </p>
                          ) : (
                            <p className="text-xs mt-0.5 text-neutral-500">
                              {t.common.never}
                            </p>
                          )}
                        </div>
                        {fetchingEntityIds.includes(entity.id) ? (
                          <div className="p-1.5">
                            <LoadingSpinner
                              size="sm"
                              className="text-gray-300 p-1.5"
                            />
                          </div>
                        ) : (
                          <button
                            onClick={e => handleRefreshEntity(entity, e)}
                            className="p-1.5 rounded-full hover:bg-gray-700 transition-colors"
                            aria-label={`Refresh ${entity.name}`}
                          >
                            <RefreshCw className="h-4 w-4 text-gray-300" />
                          </button>
                        )}
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
                        className="px-4 py-1.5 text-sm text-neutral-100 flex items-center justify-between hover:bg-neutral-800/50 border-b border-neutral-700/60 last:border-b-0"
                      >
                        <div>
                          <div className="flex items-center gap-2">
                            <span>{t.common.crypto}</span>
                            <span className="text-xs text-neutral-500">
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
                              {formatTimeAgo(lastUpdatedAt, t)}
                            </p>
                          ) : (
                            <p className="text-xs mt-0.5 text-neutral-500">
                              {t.common.never}
                            </p>
                          )}
                        </div>
                        {isCryptoFetching ? (
                          <div className="p-1.5">
                            <LoadingSpinner
                              size="sm"
                              className="text-gray-300 p-1.5"
                            />
                          </div>
                        ) : (
                          <button
                            onClick={handleRefreshCrypto}
                            className="p-1.5 rounded-full hover:bg-gray-700 transition-colors"
                            aria-label={`Refresh ${t.common.crypto}`}
                          >
                            <RefreshCw className="h-4 w-4 text-gray-300" />
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
