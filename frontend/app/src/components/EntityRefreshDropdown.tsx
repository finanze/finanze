import type React from 'react'
import { motion, AnimatePresence } from 'framer-motion'

import { useState, useMemo } from 'react'
import { Button } from '@/components/ui/Button'
import { useAppContext } from '@/context/AppContext'
import { useFinancialData } from '@/context/FinancialDataContext'
import { useI18n } from '@/i18n'
import { Entity, EntityStatus } from '@/types'
import { Database, RefreshCw, History, ChevronDown } from 'lucide-react'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { formatTimeAgo } from '@/lib/timeUtils'

export function EntityRefreshDropdown() {
    const { entities, scrape } = useAppContext()
    const { positionsData } = useFinancialData()
    const { t } = useI18n()
    const [isOpen, setIsOpen] = useState(false)
    const [refreshingEntityIds, setRefreshingEntityIds] = useState<string[]>([])

    const connectedEntities =
        entities?.filter(
            (entity) =>
                entity.status === EntityStatus.CONNECTED && entity.is_real
        ) || []

    const handleRefreshEntity = async (entity: Entity, e: React.MouseEvent) => {
        e.stopPropagation()

        if (!entity) return

        try {
            setRefreshingEntityIds((prev) => [...prev, entity.id])

            const features = entity.features || []
            const options = { avoidNewLogin: true }
            await scrape(entity, features, options)
        } finally {
            setRefreshingEntityIds((prev) =>
                prev.filter((id) => id !== entity.id)
            )
        }
    }

    const isUpdateOld = (date: Date | null): boolean => {
        if (!date) return false
        const now = new Date()
        const diffTime = now.getTime() - date.getTime()
        const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24))
        return diffDays > 7
    }

    const entitiesWithLastUpdate = useMemo(() => {
        if (!connectedEntities || !positionsData?.positions) {
            return []
        }

        return connectedEntities
            .map((entity) => {
                const globalPosition = positionsData.positions[entity.id]
                const lastUpdatedAt = globalPosition
                    ? new Date(globalPosition.date)
                    : null
                return { entity, lastUpdatedAt }
            })
            .sort((a, b) => {
                if (a.lastUpdatedAt && b.lastUpdatedAt) {
                    return b.lastUpdatedAt.getTime() - a.lastUpdatedAt.getTime()
                }
                if (a.lastUpdatedAt) return -1
                if (b.lastUpdatedAt) return 1
                return a.entity.name.localeCompare(b.entity.name)
            })
    }, [connectedEntities, positionsData])

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
                {refreshingEntityIds.length > 0 ? (
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
                        transition={{ duration: 0.2, ease: 'easeInOut' }}
                        className="absolute right-0 mt-2 w-72 rounded-md shadow-lg bg-neutral-950/80 backdrop-blur-md border border-neutral-700/50 z-50"
                    >
                        <div
                            className="py-1"
                            role="menu"
                            aria-orientation="vertical"
                        >
                            <div className="px-4 py-3 text-sm font-medium text-neutral-400 border-b border-neutral-700/50 flex items-center">
                                <History className="h-4 w-4 mr-2 text-neutral-500" />
                                {t.entities.refreshEntity}
                            </div>
                            <div className="max-h-80 overflow-y-auto">
                                {entitiesWithLastUpdate.map(
                                    ({ entity, lastUpdatedAt }) => {
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
                                                                isUpdateOld(
                                                                    lastUpdatedAt
                                                                )
                                                                    ? 'text-orange-300'
                                                                    : 'text-neutral-400'
                                                            }`}
                                                        >
                                                            {formatTimeAgo(
                                                                lastUpdatedAt,
                                                                t
                                                            )}
                                                        </p>
                                                    ) : (
                                                        <p className="text-xs mt-0.5 text-neutral-500">
                                                            {t.common.never}
                                                        </p>
                                                    )}
                                                </div>
                                                {refreshingEntityIds.includes(
                                                    entity.id
                                                ) ? (
                                                    <div className="p-1.5">
                                                        <LoadingSpinner
                                                            size="sm"
                                                            className="text-gray-300 p-1.5"
                                                        />
                                                    </div>
                                                ) : (
                                                    <button
                                                        onClick={(e) =>
                                                            handleRefreshEntity(
                                                                entity,
                                                                e
                                                            )
                                                        }
                                                        className="p-1.5 rounded-full hover:bg-gray-700 transition-colors"
                                                        aria-label={`Refresh ${entity.name}`}
                                                    >
                                                        <RefreshCw className="h-4 w-4 text-gray-300" />
                                                    </button>
                                                )}
                                            </div>
                                        )
                                    }
                                )}
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {isOpen && (
                <div
                    className="fixed inset-0 z-40"
                    onClick={() => setIsOpen(false)}
                />
            )}
        </div>
    )
}
