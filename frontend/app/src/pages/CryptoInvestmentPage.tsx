import React, { useMemo, useState, useCallback, useRef, useEffect } from "react"
import { useI18n } from "@/i18n"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useAppContext } from "@/context/AppContext"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { ConfirmationDialog } from "@/components/ui/ConfirmationDialog"
import { EditDialog } from "@/components/ui/EditDialog"
import { InvestmentFilters } from "@/components/InvestmentFilters"
import { InvestmentDistributionChart } from "@/components/InvestmentDistributionChart"
import {
  formatCurrency,
  formatNumber,
  formatPercentage,
} from "@/lib/formatters"
import { copyToClipboard } from "@/lib/clipboard"
import {
  calculateCryptoAssetInitialInvestment,
  calculateCryptoAssetValue,
  calculateInvestmentDistribution,
  convertCurrency,
  getWalletAssets,
} from "@/utils/financialDataUtils"
import {
  ProductType,
  CryptoCurrencyWallet,
  CryptoCurrencyPosition,
  CryptoCurrencyType,
} from "@/types/position"
import {
  DataSource,
  type Entity,
  type EntityType,
  type EntityOrigin,
  type ExchangeRates,
} from "@/types"
import {
  ArrowLeft,
  TrendingUp,
  TrendingDown,
  Copy,
  Check,
  Plus,
  Wallet,
  Edit3,
  Trash2,
  MoreVertical,
} from "lucide-react"
import { getIconForAssetType } from "@/utils/dashboardUtils"
import { PinAssetButton } from "@/components/ui/PinAssetButton"
import { useNavigate } from "react-router-dom"
import { MultiSelectOption } from "@/components/ui/MultiSelect"
import { AnimatePresence, motion } from "framer-motion"
import { fadeListContainer, fadeListItem } from "@/lib/animations"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs"
import { deleteCryptoWallet, updateCryptoWallet } from "@/services/api"
import {
  ManualPositionsManager,
  ManualPositionsControls,
  ManualPositionsUnsavedNotice,
  useManualPositions,
} from "@/components/manual/ManualPositionsManager"
import type { ManualPositionDraft } from "@/components/manual/manualPositionTypes"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"

interface WalletAssetView {
  asset: CryptoCurrencyPosition
  symbol: string
  displayName: string
  value: number
  valueAvailable: boolean
  initialInvestment: number
  roi: number | null
  amount: number
  isToken: boolean
  iconUrl: string | null
  hasAssetDetails: boolean
  groupingKey: string
  isManual: boolean
  originalId?: string
  localId?: string
}

interface WalletWithComputed {
  wallet: CryptoCurrencyWallet
  assets: WalletAssetView[]
  nativeAssets: WalletAssetView[]
  tokenAssets: WalletAssetView[]
  totalValue: number
  totalInitialInvestment: number
}

interface EntityWalletGroup {
  entity: Pick<Entity, "id" | "name"> & {
    type?: EntityType
    origin?: EntityOrigin
    icon_url?: string | null
  }
  wallets: WalletWithComputed[]
  totalValue: number
  totalInitialInvestment: number
}

interface NetworkAssetSummary {
  key: string
  groupingKey: string
  displayName: string
  symbol: string
  iconUrl: string | null
  totalValue: number
  valueAvailable: boolean
  totalInitialInvestment: number
  roi: number | null
  totalAmount: number
  wallets: Array<{
    id: string
    name: string
    address: string
  }>
}

interface EntityNetworkGroup {
  entity: Pick<Entity, "id" | "name"> & {
    origin?: EntityOrigin
    icon_url?: string | null
  }
  totalValue: number
  assets: NetworkAssetSummary[]
}

type ViewMode = "wallets" | "network"

const getWalletIdentifier = (wallet: CryptoCurrencyWallet): string => {
  return (
    wallet.id ??
    wallet.address ??
    `wallet-${Math.random().toString(36).slice(2)}`
  )
}

const isWalletlessEntry = (wallet: CryptoCurrencyWallet): boolean => {
  return !wallet.id && !wallet.address
}

const hasExchangeRateEntry = (
  exchangeRates: ExchangeRates | null | undefined,
  targetCurrency: string,
  key: string | null | undefined,
): boolean => {
  if (!exchangeRates || !key) {
    return false
  }

  const normalizedTarget = targetCurrency.toUpperCase()
  const targetRates =
    exchangeRates[targetCurrency] ?? exchangeRates[normalizedTarget]
  if (!targetRates) {
    return false
  }

  const variants = [key, key.toUpperCase(), key.toLowerCase()]
  return variants.some(variant => targetRates[variant] != null)
}

const hasSymbolConversion = (
  symbol: string | null | undefined,
  targetCurrency: string,
  exchangeRates: ExchangeRates | null | undefined,
) => {
  if (!symbol) return false
  return hasExchangeRateEntry(exchangeRates, targetCurrency, symbol)
}

const canConvertMarketValue = (
  currency: string | null | undefined,
  targetCurrency: string,
  exchangeRates: ExchangeRates | null | undefined,
) => {
  if (!currency) return false
  if (currency === targetCurrency) return true
  return hasExchangeRateEntry(exchangeRates, targetCurrency, currency)
}

interface WalletOwnershipBadgeProps {
  wallets: NetworkAssetSummary["wallets"]
  label: string
  countLabel: string
}

function WalletOwnershipBadge({
  wallets,
  label,
  countLabel,
}: WalletOwnershipBadgeProps) {
  const [open, setOpen] = useState(false)
  const closeTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clearCloseTimeout = useCallback(() => {
    if (closeTimeoutRef.current) {
      clearTimeout(closeTimeoutRef.current)
      closeTimeoutRef.current = null
    }
  }, [])

  const handleOpenChange = useCallback(
    (nextOpen: boolean) => {
      setOpen(nextOpen)
      if (!nextOpen) {
        clearCloseTimeout()
      }
    },
    [clearCloseTimeout],
  )

  const handlePointerEnter = useCallback(() => {
    clearCloseTimeout()
    setOpen(true)
  }, [clearCloseTimeout])

  const handlePointerLeave = useCallback(() => {
    clearCloseTimeout()
    closeTimeoutRef.current = setTimeout(() => setOpen(false), 120)
  }, [clearCloseTimeout])

  useEffect(() => {
    return () => {
      clearCloseTimeout()
    }
  }, [clearCloseTimeout])

  if (wallets.length === 0) {
    return null
  }

  const walletCount = wallets.length

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <button
          type="button"
          onMouseEnter={handlePointerEnter}
          onMouseLeave={handlePointerLeave}
          className="inline-flex items-center gap-1 rounded-full border border-border bg-muted/60 px-2 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
          aria-label={`${label} · ${walletCount} ${countLabel}`}
        >
          <Wallet className="h-3 w-3" />
          {walletCount}
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        sideOffset={8}
        className="w-64 space-y-3 p-3"
        onMouseEnter={handlePointerEnter}
        onMouseLeave={handlePointerLeave}
      >
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <ul className="space-y-2">
          {wallets.map(wallet => (
            <li key={wallet.id} className="flex flex-col gap-1">
              <span className="text-sm font-medium text-foreground">
                {wallet.name}
              </span>
              <span className="text-xs font-mono text-muted-foreground">
                ...{wallet.address.slice(-6)}
              </span>
            </li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  )
}

interface WalletActionsMenuProps {
  onEdit: () => void
  onDelete: () => void
  disabled?: boolean
}

function WalletActionsMenu({
  onEdit,
  onDelete,
  disabled,
}: WalletActionsMenuProps) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)

  const handleEdit = useCallback(() => {
    onEdit()
    setOpen(false)
  }, [onEdit])

  const handleDelete = useCallback(() => {
    onDelete()
    setOpen(false)
  }, [onDelete])

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground"
          disabled={disabled}
          type="button"
        >
          <MoreVertical className="h-4 w-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" sideOffset={8} className="w-44 p-2 space-y-1">
        <button
          type="button"
          onClick={handleEdit}
          className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm font-medium text-left transition-colors hover:bg-accent hover:text-accent-foreground"
        >
          <Edit3 className="h-3.5 w-3.5" />
          {t.common.edit}
        </button>
        <button
          type="button"
          onClick={handleDelete}
          className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm font-medium text-left text-red-600 transition-colors hover:bg-red-50 hover:text-red-700 dark:hover:bg-red-500/10"
        >
          <Trash2 className="h-3.5 w-3.5" />
          {t.common.delete}
        </button>
      </PopoverContent>
    </Popover>
  )
}

export default function CryptoInvestmentPage() {
  const { positionsData, isLoading } = useFinancialData()
  const { settings, exchangeRates, entities } = useAppContext()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <ManualPositionsManager asset="crypto">
      <CryptoInvestmentContent
        positionsData={positionsData}
        settings={settings}
        exchangeRates={exchangeRates}
        entities={entities}
      />
    </ManualPositionsManager>
  )
}

interface CryptoInvestmentContentProps {
  positionsData: ReturnType<typeof useFinancialData>["positionsData"]
  settings: ReturnType<typeof useAppContext>["settings"]
  exchangeRates: ReturnType<typeof useAppContext>["exchangeRates"]
  entities: ReturnType<typeof useAppContext>["entities"]
}

function CryptoInvestmentContent({
  positionsData,
  settings,
  exchangeRates,
  entities,
}: CryptoInvestmentContentProps) {
  const { t, locale } = useI18n()
  const navigate = useNavigate()
  const { refreshEntity } = useFinancialData()
  const {
    drafts,
    isEntryDeleted,
    isEditMode,
    editByOriginalId,
    editByLocalId,
    deleteByOriginalId,
    deleteByLocalId,
  } = useManualPositions()

  const cryptoDrafts = drafts as ManualPositionDraft<CryptoCurrencyPosition>[]

  const draftsByOriginalId = useMemo(() => {
    const map = new Map<string, ManualPositionDraft<CryptoCurrencyPosition>>()
    cryptoDrafts.forEach(draft => {
      const id = draft.originalId
      if (!id) return
      if (isEntryDeleted(id)) return
      map.set(id, draft)
    })
    return map
  }, [cryptoDrafts, isEntryDeleted])

  const [selectedEntities, setSelectedEntities] = useState<string[]>([])
  const [selectedWalletFilters, setSelectedWalletFilters] = useState<string[]>(
    [],
  )
  const [copiedAddress, setCopiedAddress] = useState<string | null>(null)
  const symbolRefs = useRef<Record<string, HTMLDivElement | null>>({})
  const [highlightedAsset, setHighlightedAsset] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>("wallets")
  const [showEditDialog, setShowEditDialog] = useState(false)
  const [walletToEdit, setWalletToEdit] = useState<CryptoCurrencyWallet | null>(
    null,
  )
  const [editWalletName, setEditWalletName] = useState("")
  const [isUpdatingWallet, setIsUpdatingWallet] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [walletToDelete, setWalletToDelete] =
    useState<CryptoCurrencyWallet | null>(null)
  const [isDeletingWallet, setIsDeletingWallet] = useState(false)
  const [editWalletEntityId, setEditWalletEntityId] = useState<string | null>(
    null,
  )
  const [deleteWalletEntityId, setDeleteWalletEntityId] = useState<
    string | null
  >(null)
  const registerAssetRef = useCallback(
    (identifier: string, element: HTMLDivElement | null) => {
      if (!identifier) return
      if (element) {
        symbolRefs.current[identifier] = element
      } else {
        delete symbolRefs.current[identifier]
      }
    },
    [],
  )

  const copyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const walletGroups = useMemo<EntityWalletGroup[]>(() => {
    if (!positionsData?.positions) {
      return []
    }

    const rates = (exchangeRates ?? {}) as ExchangeRates
    const defaultCurrency = settings.general.defaultCurrency
    const hideUnknownTokens =
      settings.assets?.crypto?.hideUnknownTokens ?? false

    return Object.values(positionsData.positions).reduce<EntityWalletGroup[]>(
      (acc, entityPosition) => {
        const entityId = entityPosition.entity?.id
        const entityName = entityPosition.entity?.name

        if (!entityId || !entityName) {
          return acc
        }

        const cryptoProduct = entityPosition.products[ProductType.CRYPTO]
        if (
          !cryptoProduct ||
          !("entries" in cryptoProduct) ||
          !Array.isArray(cryptoProduct.entries) ||
          cryptoProduct.entries.length === 0
        ) {
          return acc
        }

        const entityData = entities?.find(e => e.id === entityId)
        const entityType = entityData?.type
        const entityOrigin = entityData?.origin
        const entityIconUrl = entityData?.icon_url
        const isCryptoWalletEntity = entityType === "CRYPTO_WALLET"
        const nativeEntityIconPath = `entities/${entityId}.png`

        const wallets = (cryptoProduct.entries as CryptoCurrencyWallet[])
          .map(wallet => {
            const walletIdentifier = getWalletIdentifier(wallet)
            const assets = getWalletAssets(wallet, { hideUnknownTokens })

            const assetViews = assets
              .map((asset): WalletAssetView | null => {
                if (asset.id && isEntryDeleted(asset.id)) {
                  return null
                }

                const draftOverride = asset.id
                  ? draftsByOriginalId.get(asset.id)
                  : undefined
                const effectiveAsset = (draftOverride ?? asset) as
                  | CryptoCurrencyPosition
                  | ManualPositionDraft<CryptoCurrencyPosition>

                const symbol =
                  effectiveAsset.symbol?.toUpperCase() ||
                  effectiveAsset.crypto_asset?.symbol?.toUpperCase() ||
                  ""
                const displayName =
                  effectiveAsset.crypto_asset?.name ||
                  effectiveAsset.name ||
                  symbol
                const hasAssetDetails = Boolean(effectiveAsset.crypto_asset)
                const value = hasAssetDetails
                  ? calculateCryptoAssetValue(
                      effectiveAsset as CryptoCurrencyPosition,
                      defaultCurrency,
                      rates,
                    )
                  : 0
                const initialInvestment = hasAssetDetails
                  ? calculateCryptoAssetInitialInvestment(
                      effectiveAsset as CryptoCurrencyPosition,
                      defaultCurrency,
                      rates,
                    )
                  : 0
                const hasSymbolRate =
                  hasAssetDetails &&
                  hasSymbolConversion(symbol, defaultCurrency, rates)
                const marketCurrency =
                  effectiveAsset.currency ||
                  effectiveAsset.investment_currency ||
                  null
                const hasMarketValue =
                  hasAssetDetails && effectiveAsset.market_value != null
                const marketValueConvertible =
                  hasAssetDetails && hasMarketValue
                    ? canConvertMarketValue(
                        marketCurrency,
                        defaultCurrency,
                        rates,
                      )
                    : false
                const valueAvailable =
                  hasAssetDetails && (hasSymbolRate || marketValueConvertible)
                const roi =
                  initialInvestment > 0
                    ? ((value - initialInvestment) / initialInvestment) * 100
                    : null
                const isToken =
                  (effectiveAsset.type ?? CryptoCurrencyType.NATIVE) ===
                    CryptoCurrencyType.TOKEN ||
                  Boolean(effectiveAsset.contract_address)
                const iconUrl = isToken
                  ? (effectiveAsset.crypto_asset?.icon_urls?.[0] ?? null)
                  : isCryptoWalletEntity && entityOrigin === "NATIVE"
                    ? nativeEntityIconPath
                    : (effectiveAsset.crypto_asset?.icon_urls?.[0] ?? null)

                const normalizedSymbol =
                  symbol ||
                  effectiveAsset.crypto_asset?.symbol?.toUpperCase() ||
                  effectiveAsset.name?.toUpperCase() ||
                  effectiveAsset.id
                const contractAddress = effectiveAsset.contract_address
                  ? effectiveAsset.contract_address.toLowerCase()
                  : null
                const tokenKey =
                  contractAddress ??
                  effectiveAsset.crypto_asset?.id?.toLowerCase()

                if (isToken && !tokenKey) {
                  return null
                }

                const groupingKey = isToken
                  ? `token:${tokenKey}`
                  : normalizedSymbol
                    ? `native:${normalizedSymbol}`
                    : `native:${walletIdentifier}:${effectiveAsset.id ?? asset.id}`

                return {
                  asset: effectiveAsset as CryptoCurrencyPosition,
                  symbol,
                  displayName,
                  value,
                  valueAvailable,
                  initialInvestment,
                  roi,
                  amount: effectiveAsset.amount ?? 0,
                  isToken,
                  iconUrl,
                  hasAssetDetails,
                  groupingKey,
                  isManual: effectiveAsset.source === DataSource.MANUAL,
                  originalId: asset.id,
                }
              })
              .filter((view): view is WalletAssetView => view !== null)

            const sortedAssetViews = [...assetViews].sort((a, b) => {
              // Prioritize by value availability: assets with available values come first
              if (a.valueAvailable !== b.valueAvailable) {
                return a.valueAvailable ? -1 : 1
              }
              // Both available or both unavailable: sort by value descending
              return b.value - a.value
            })

            const nativeAssets = sortedAssetViews.filter(view => !view.isToken)
            const tokenAssets = sortedAssetViews.filter(view => view.isToken)

            const totalValue = sortedAssetViews.reduce(
              (sum, view) => sum + view.value,
              0,
            )
            const totalInitialInvestment = sortedAssetViews.reduce(
              (sum, view) => sum + view.initialInvestment,
              0,
            )

            return {
              wallet,
              assets: sortedAssetViews,
              nativeAssets,
              tokenAssets,
              totalValue,
              totalInitialInvestment,
            }
          })
          .sort((a, b) => b.totalValue - a.totalValue)

        const entityTotalValue = wallets.reduce(
          (sum, wallet) => sum + wallet.totalValue,
          0,
        )
        const entityTotalInitialInvestment = wallets.reduce(
          (sum, wallet) => sum + wallet.totalInitialInvestment,
          0,
        )

        acc.push({
          entity: {
            id: entityId,
            name: entityName,
            type: entityType,
            origin: entityOrigin,
            icon_url: entityIconUrl,
          },
          wallets,
          totalValue: entityTotalValue,
          totalInitialInvestment: entityTotalInitialInvestment,
        })

        return acc
      },
      [],
    )
  }, [
    positionsData,
    exchangeRates,
    settings.general.defaultCurrency,
    settings.assets?.crypto?.hideUnknownTokens,
    entities,
    draftsByOriginalId,
    isEntryDeleted,
  ])

  const walletGroupsWithDrafts = useMemo<EntityWalletGroup[]>(() => {
    const result: EntityWalletGroup[] = walletGroups.map(group => ({
      ...group,
      wallets: [...group.wallets],
    }))
    const defaultCurrency = settings.general.defaultCurrency
    const rates = (exchangeRates ?? {}) as ExchangeRates

    const draftsByEntity = new Map<
      string,
      ManualPositionDraft<CryptoCurrencyPosition>[]
    >()

    cryptoDrafts.forEach(draft => {
      if (isEntryDeleted(draft.originalId ?? "")) return
      const entityId = draft.entityId
      if (!entityId) return
      if (!draftsByEntity.has(entityId)) {
        draftsByEntity.set(entityId, [])
      }
      draftsByEntity.get(entityId)!.push(draft)
    })

    draftsByEntity.forEach((entityDrafts, entityId) => {
      const existingGroup = result.find(g => g.entity.id === entityId)

      const draftAssets: WalletAssetView[] = entityDrafts
        .filter(draft => !draft.originalId)
        .map(draft => {
          const symbol = draft.symbol?.toUpperCase() || ""
          const displayName = draft.name || symbol
          const hasAssetDetails = Boolean(draft.crypto_asset)
          const isToken =
            (draft.type ?? CryptoCurrencyType.NATIVE) ===
              CryptoCurrencyType.TOKEN || Boolean(draft.contract_address)
          const groupingKey = isToken
            ? `token:${draft.contract_address?.toLowerCase() || draft.localId}`
            : `native:${symbol || draft.localId}`

          let value = 0
          let valueAvailable = false

          if (draft.market_value != null && draft.market_value > 0) {
            const draftCurrency = draft.currency || defaultCurrency
            if (draftCurrency === defaultCurrency) {
              value = draft.market_value
            } else {
              value = convertCurrency(
                draft.market_value,
                draftCurrency,
                defaultCurrency,
                rates,
              )
            }
            valueAvailable = value > 0
          } else if (hasAssetDetails && symbol) {
            value = calculateCryptoAssetValue(
              draft as unknown as CryptoCurrencyPosition,
              defaultCurrency,
              rates,
            )
            valueAvailable = value > 0
          }

          const initialInvestment = calculateCryptoAssetInitialInvestment(
            draft as unknown as CryptoCurrencyPosition,
            defaultCurrency,
            rates,
          )

          const roi =
            initialInvestment > 0 && value > 0
              ? ((value - initialInvestment) / initialInvestment) * 100
              : null

          return {
            asset: draft as unknown as CryptoCurrencyPosition,
            symbol,
            displayName,
            value,
            valueAvailable,
            initialInvestment,
            roi,
            amount: draft.amount ?? 0,
            isToken,
            iconUrl: draft.crypto_asset?.icon_urls?.[0] ?? null,
            hasAssetDetails,
            groupingKey,
            isManual: true,
            originalId: draft.originalId,
            localId: draft.localId,
          }
        })

      if (draftAssets.length === 0) return

      const totalValue = draftAssets.reduce((sum, a) => sum + a.value, 0)
      const totalInitialInvestment = draftAssets.reduce(
        (sum, a) => sum + a.initialInvestment,
        0,
      )

      if (existingGroup) {
        const walletWithDrafts: WalletWithComputed = {
          wallet: { name: null, assets: [] },
          assets: draftAssets,
          nativeAssets: draftAssets.filter(a => !a.isToken),
          tokenAssets: draftAssets.filter(a => a.isToken),
          totalValue,
          totalInitialInvestment,
        }
        existingGroup.wallets.push(walletWithDrafts)
        existingGroup.totalValue += totalValue
        existingGroup.totalInitialInvestment += totalInitialInvestment
      } else {
        const entityData = entities?.find(e => e.id === entityId)
        const draftEntity = entityDrafts[0]
        const draftAny = draftEntity as any
        const entityName =
          entityData?.name ||
          draftEntity.entityName ||
          draftEntity.newEntityName ||
          "New Entity"
        const entityIconUrl =
          entityData?.icon_url || draftAny._new_entity_icon_url || null
        const entityType =
          entityData?.type || draftAny._entity_type || "CRYPTO_WALLET"
        const entityOrigin = entityData?.origin ?? ("MANUAL" as EntityOrigin)

        const newGroup: EntityWalletGroup = {
          entity: {
            id: entityId,
            name: entityName,
            type: entityType,
            origin: entityOrigin,
            icon_url: entityIconUrl,
          },
          wallets: [
            {
              wallet: { name: null, assets: [] },
              assets: draftAssets,
              nativeAssets: draftAssets.filter(a => !a.isToken),
              tokenAssets: draftAssets.filter(a => a.isToken),
              totalValue,
              totalInitialInvestment,
            },
          ],
          totalValue,
          totalInitialInvestment,
        }
        result.push(newGroup)
      }
    })

    return result
  }, [
    walletGroups,
    cryptoDrafts,
    entities,
    isEntryDeleted,
    settings.general.defaultCurrency,
    exchangeRates,
  ])

  const entityOptions = useMemo<MultiSelectOption[]>(() => {
    const unique = new Map<string, string>()
    walletGroupsWithDrafts.forEach(group => {
      unique.set(group.entity.id, group.entity.name)
    })
    return Array.from(unique.entries()).map(([value, label]) => ({
      value,
      label,
    }))
  }, [walletGroupsWithDrafts])

  const entityFilteredWalletGroups = useMemo<EntityWalletGroup[]>(() => {
    if (selectedEntities.length === 0) {
      return walletGroupsWithDrafts
    }
    return walletGroupsWithDrafts.filter(group =>
      selectedEntities.includes(group.entity.id),
    )
  }, [walletGroupsWithDrafts, selectedEntities])

  const walletFilterOptions = useMemo<MultiSelectOption[]>(() => {
    return entityFilteredWalletGroups.flatMap(group =>
      group.wallets.map(walletGroup => {
        const wallet = walletGroup.wallet
        const walletName = wallet.name ?? wallet.address ?? group.entity.name
        return {
          value: getWalletIdentifier(wallet),
          label: `${group.entity.name} - ${walletName}`,
        }
      }),
    )
  }, [entityFilteredWalletGroups])

  const filteredCryptoWallets = useMemo<EntityWalletGroup[]>(() => {
    if (selectedWalletFilters.length === 0) {
      return entityFilteredWalletGroups
    }

    const selected = new Set(selectedWalletFilters)

    return entityFilteredWalletGroups
      .map(group => {
        const filteredWallets = group.wallets.filter(walletGroup =>
          selected.has(getWalletIdentifier(walletGroup.wallet)),
        )

        if (filteredWallets.length === 0) {
          return null
        }

        const totalValue = filteredWallets.reduce(
          (sum, wallet) => sum + wallet.totalValue,
          0,
        )
        const totalInitialInvestment = filteredWallets.reduce(
          (sum, wallet) => sum + wallet.totalInitialInvestment,
          0,
        )

        return {
          entity: group.entity,
          wallets: filteredWallets,
          totalValue,
          totalInitialInvestment,
        }
      })
      .filter((group): group is EntityWalletGroup => group !== null)
  }, [entityFilteredWalletGroups, selectedWalletFilters])

  useEffect(() => {
    setSelectedWalletFilters(prevFilters => {
      if (prevFilters.length === 0) {
        return prevFilters
      }

      const availableWalletIds = new Set(
        entityFilteredWalletGroups.flatMap(group =>
          group.wallets.map(walletGroup =>
            getWalletIdentifier(walletGroup.wallet),
          ),
        ),
      )

      const nextFilters = prevFilters.filter(id => availableWalletIds.has(id))

      return nextFilters.length === prevFilters.length
        ? prevFilters
        : nextFilters
    })
  }, [entityFilteredWalletGroups])

  const networkGroups = useMemo<EntityNetworkGroup[]>(() => {
    return filteredCryptoWallets.map(entityGroup => {
      const assetMap = new Map<
        string,
        {
          groupingKey: string
          displayName: string
          symbol: string
          iconUrl: string | null
          totalValue: number
          valueAvailable: boolean
          totalInitialInvestment: number
          totalAmount: number
          wallets: Map<
            string,
            {
              id: string
              name: string
              address: string
            }
          >
        }
      >()
      entityGroup.wallets.forEach(walletGroup => {
        const walletName =
          walletGroup.wallet.name ??
          walletGroup.wallet.address ??
          entityGroup.entity.name
        const walletId = getWalletIdentifier(walletGroup.wallet)
        const walletAddress = walletGroup.wallet.address
        const walletKey = walletAddress ? walletAddress.toLowerCase() : walletId

        walletGroup.assets.forEach(assetView => {
          const assetKey = assetView.groupingKey
          const existing = assetMap.get(assetKey)
          if (existing) {
            existing.totalValue += assetView.value
            existing.totalInitialInvestment += assetView.initialInvestment
            existing.totalAmount += assetView.amount
            existing.valueAvailable =
              existing.valueAvailable || assetView.valueAvailable
            if (walletAddress) {
              existing.wallets.set(walletKey, {
                id: walletId,
                name: walletName,
                address: walletAddress,
              })
            }
          } else {
            const wallets = new Map<
              string,
              {
                id: string
                name: string
                address: string
              }
            >()
            if (walletAddress) {
              wallets.set(walletKey, {
                id: walletId,
                name: walletName,
                address: walletAddress,
              })
            }
            assetMap.set(assetKey, {
              groupingKey: assetKey,
              displayName: assetView.displayName,
              symbol: assetView.symbol || assetView.displayName || assetKey,
              iconUrl: assetView.iconUrl,
              totalValue: assetView.value,
              valueAvailable: assetView.valueAvailable,
              totalInitialInvestment: assetView.initialInvestment,
              totalAmount: assetView.amount,
              wallets,
            })
          }
        })
      })

      const assets: NetworkAssetSummary[] = Array.from(assetMap.values())
        .map(entry => {
          const wallets = Array.from(entry.wallets.values())
          const roi =
            entry.valueAvailable && entry.totalInitialInvestment > 0
              ? ((entry.totalValue - entry.totalInitialInvestment) /
                  entry.totalInitialInvestment) *
                100
              : null

          return {
            key: `${entityGroup.entity.id}-${entry.groupingKey}`,
            groupingKey: entry.groupingKey,
            displayName: entry.displayName,
            symbol: entry.symbol,
            iconUrl: entry.iconUrl,
            totalValue: entry.totalValue,
            valueAvailable: entry.valueAvailable,
            totalInitialInvestment: entry.totalInitialInvestment,
            roi,
            totalAmount: entry.totalAmount,
            wallets,
          }
        })
        .sort((a, b) => b.totalValue - a.totalValue)

      return {
        entity: entityGroup.entity,
        totalValue: entityGroup.totalValue,
        assets,
      }
    })
  }, [filteredCryptoWallets])

  const totalFilteredWallets = useMemo(
    () =>
      filteredCryptoWallets.reduce(
        (sum, group) =>
          sum +
          group.wallets.filter(
            walletGroup => !isWalletlessEntry(walletGroup.wallet),
          ).length,
        0,
      ),
    [filteredCryptoWallets],
  )

  const allAssets = useMemo(() => {
    return filteredCryptoWallets.flatMap(group =>
      group.wallets.flatMap(wallet => wallet.assets),
    )
  }, [filteredCryptoWallets])

  const totalValue = useMemo(
    () =>
      filteredCryptoWallets.reduce((sum, group) => sum + group.totalValue, 0),
    [filteredCryptoWallets],
  )

  const formattedTotalValue = useMemo(
    () => formatCurrency(totalValue, locale, settings.general.defaultCurrency),
    [totalValue, locale, settings.general.defaultCurrency],
  )

  const totalCryptoAssets = useMemo(() => {
    const uniqueIdentifiers = new Set<string>()
    filteredCryptoWallets.forEach(group =>
      group.wallets.forEach(wallet =>
        wallet.assets.forEach(asset => {
          uniqueIdentifiers.add(asset.groupingKey)
        }),
      ),
    )
    return uniqueIdentifiers.size
  }, [filteredCryptoWallets])

  const chartPositions = useMemo(
    () =>
      allAssets
        .filter(asset => asset.value > 0)
        .map(asset => ({
          symbol: asset.groupingKey,
          name: asset.displayName,
          currentValue: asset.value,
        })),
    [allAssets],
  )

  const chartLabelMap = useMemo(() => {
    const map = new Map<string, string>()
    chartPositions.forEach(position => {
      if (!map.has(position.symbol)) {
        map.set(position.symbol, position.name ?? position.symbol)
      }
    })
    return map
  }, [chartPositions])

  const chartData = useMemo(() => {
    const distribution = calculateInvestmentDistribution(
      chartPositions,
      "symbol",
    )
    return distribution.map(item => {
      const identifier = item.name
      const label = chartLabelMap.get(identifier) ?? identifier
      return {
        ...item,
        name: label,
        id: identifier,
      }
    })
  }, [chartPositions, chartLabelMap])

  const chartColorMap = useMemo(() => {
    const colorMap = new Map<string, string>()
    chartData.forEach(item => {
      const key = (item as { id?: string }).id ?? item.name
      colorMap.set(key, item.color)
    })
    return colorMap
  }, [chartData])

  const handleCopyAddress = useCallback(
    (address: string) => {
      if (!address) return

      const performCopy = async () => {
        try {
          const ok = await copyToClipboard(address)
          if (!ok) return

          setCopiedAddress(address)
          if (copyTimeoutRef.current) {
            clearTimeout(copyTimeoutRef.current)
          }
          copyTimeoutRef.current = setTimeout(() => {
            setCopiedAddress(prev => (prev === address ? null : prev))
          }, 1500)
        } catch (error) {
          console.warn("Failed to copy wallet address", error)
        }
      }

      void performCopy()
    },
    [setCopiedAddress],
  )

  const handleEditWallet = (wallet: CryptoCurrencyWallet, entityId: string) => {
    setWalletToEdit(wallet)
    setEditWalletName(wallet.name ?? wallet.address ?? "")
    setEditWalletEntityId(entityId)
    setShowEditDialog(true)
  }

  const confirmEditWallet = async () => {
    const trimmedName = editWalletName.trim()
    if (!walletToEdit || !trimmedName || !walletToEdit.id) {
      return
    }

    if (trimmedName === walletToEdit.name) {
      setShowEditDialog(false)
      setWalletToEdit(null)
      setEditWalletName("")
      setEditWalletEntityId(null)
      return
    }

    setIsUpdatingWallet(true)
    try {
      await updateCryptoWallet({
        id: walletToEdit.id,
        name: trimmedName,
      })

      try {
        if (editWalletEntityId) {
          await refreshEntity(editWalletEntityId)
        } else {
          await refreshEntity("crypto")
        }
      } catch (refreshError) {
        console.error(
          "Error refreshing crypto data after wallet update:",
          refreshError,
        )
      }

      setShowEditDialog(false)
      setWalletToEdit(null)
      setEditWalletName("")
      setEditWalletEntityId(null)
    } catch (error) {
      console.error("Error updating wallet:", error)
    } finally {
      setIsUpdatingWallet(false)
    }
  }

  const handleDeleteWallet = (
    wallet: CryptoCurrencyWallet,
    entityId: string,
  ) => {
    if (!wallet.id) {
      console.error("Cannot delete wallet without ID", wallet)
      return
    }
    setWalletToDelete(wallet)
    setShowDeleteConfirm(true)
    setDeleteWalletEntityId(entityId)
  }

  const confirmDeleteWallet = async () => {
    if (!walletToDelete?.id) {
      return
    }

    setIsDeletingWallet(true)
    try {
      await deleteCryptoWallet(walletToDelete.id)
      try {
        if (deleteWalletEntityId) {
          await refreshEntity(deleteWalletEntityId)
        } else {
          await refreshEntity("crypto")
        }
      } catch (refreshError) {
        console.error(
          "Error refreshing crypto data after wallet deletion:",
          refreshError,
        )
      }

      setShowDeleteConfirm(false)
      setWalletToDelete(null)
      setDeleteWalletEntityId(null)
    } catch (error) {
      console.error("Error deleting wallet:", error)
    } finally {
      setIsDeletingWallet(false)
    }
  }

  const handleViewAllTokens = useCallback((wallet: CryptoCurrencyWallet) => {
    setSelectedWalletFilters([getWalletIdentifier(wallet)])
    setViewMode("network")
  }, [])

  useEffect(() => {
    return () => {
      if (copyTimeoutRef.current) {
        clearTimeout(copyTimeoutRef.current)
      }
    }
  }, [])

  const noResults = filteredCryptoWallets.length === 0
  const hasActiveFilters =
    selectedEntities.length > 0 || selectedWalletFilters.length > 0
  const cryptoWalletsLabel =
    t.entities?.cryptoWallets ?? t.walletManagement.wallets

  const walletView = (
    <motion.div
      key={`wallets-${filteredCryptoWallets.length}-${totalFilteredWallets}`}
      variants={fadeListContainer}
      initial="hidden"
      animate="show"
      className="space-y-8 pb-6"
    >
      {filteredCryptoWallets.map(entityGroup => (
        <motion.section
          key={entityGroup.entity.id}
          variants={fadeListItem}
          className="space-y-4"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {(entityGroup.entity.origin === "NATIVE" ||
                entityGroup.entity.icon_url) && (
                <div
                  className={`w-10 h-10 flex-shrink-0 overflow-hidden ${
                    entityGroup.entity.origin === "MANUAL"
                      ? "rounded-full"
                      : "rounded-md"
                  }`}
                >
                  <img
                    src={
                      entityGroup.entity.origin !== "NATIVE" &&
                      entityGroup.entity.icon_url
                        ? entityGroup.entity.icon_url
                        : `entities/${entityGroup.entity.id}.png`
                    }
                    alt={entityGroup.entity.name}
                    className={`h-full w-full ${
                      entityGroup.entity.origin === "MANUAL"
                        ? "object-cover"
                        : "object-contain"
                    }`}
                    onError={event => {
                      event.currentTarget.style.display = "none"
                    }}
                  />
                </div>
              )}
              <div>
                <h3 className="text-xl font-semibold">
                  {entityGroup.entity.name}
                </h3>
                {(() => {
                  const walletCount = entityGroup.wallets.filter(
                    walletGroup => !isWalletlessEntry(walletGroup.wallet),
                  ).length
                  if (walletCount === 0) return null
                  return (
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      {walletCount}{" "}
                      {walletCount !== 1
                        ? t.walletManagement.wallets
                        : t.walletManagement.wallet}
                    </p>
                  )
                })()}
              </div>
            </div>
            <div className="text-right">
              <div className="text-2xl font-bold">
                {formatCurrency(
                  entityGroup.totalValue,
                  locale,
                  settings.general.defaultCurrency,
                )}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">
                {t.walletManagement.totalValue}
              </div>
            </div>
          </div>
          <div className="grid gap-4 grid-cols-1 md:grid-cols-2 xl:grid-cols-3">
            {entityGroup.wallets
              .filter(walletGroup => !isWalletlessEntry(walletGroup.wallet))
              .map(walletGroup => {
                const {
                  wallet,
                  nativeAssets,
                  tokenAssets,
                  totalValue: walletTotalValue,
                } = walletGroup
                const hasAssets = walletGroup.assets.length > 0
                const walletName =
                  wallet.name ?? wallet.address ?? entityGroup.entity.name
                const walletKey = getWalletIdentifier(wallet)
                return (
                  <div
                    key={walletKey}
                    className={`flex h-full flex-col gap-4 rounded-lg border p-4 transition-all ${hasAssets ? "bg-white dark:bg-gray-900 hover:shadow-sm" : "border-dashed bg-gray-50 dark:bg-gray-900/50 opacity-75"}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        <div className="w-8 h-8 flex items-center justify-center flex-shrink-0">
                          <div className="p-1.5 bg-blue-100 dark:bg-blue-900 rounded-lg">
                            <Wallet className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                          </div>
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <h4 className="font-medium truncate">
                              {walletName}
                            </h4>
                            {!hasAssets && (
                              <span className="text-xs bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400 px-2 py-1 rounded flex-shrink-0">
                                {t.common.noDataAvailable}
                              </span>
                            )}
                          </div>
                          {wallet.address && (
                            <div className="flex items-center gap-2 group">
                              <p className="text-sm text-gray-600 dark:text-gray-400 font-mono truncate">
                                {wallet.address.slice(0, 8)}...
                                {wallet.address.slice(-6)}
                              </p>
                              <Button
                                variant="ghost"
                                size="sm"
                                className={`p-1 h-6 w-6 opacity-70 hover:opacity-100 transition-all duration-200 flex-shrink-0 ${
                                  copiedAddress === wallet.address
                                    ? "text-green-600 dark:text-green-400"
                                    : "text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                                }`}
                                onClick={() =>
                                  handleCopyAddress(wallet.address!)
                                }
                                title={
                                  copiedAddress === wallet.address
                                    ? t.common.copied
                                    : t.common.copy
                                }
                              >
                                {copiedAddress === wallet.address ? (
                                  <Check className="h-3 w-3" />
                                ) : (
                                  <Copy className="h-3 w-3" />
                                )}
                              </Button>
                            </div>
                          )}
                        </div>
                      </div>
                      <WalletActionsMenu
                        onEdit={() =>
                          handleEditWallet(wallet, entityGroup.entity.id)
                        }
                        onDelete={() =>
                          handleDeleteWallet(wallet, entityGroup.entity.id)
                        }
                        disabled={isUpdatingWallet || isDeletingWallet}
                      />
                    </div>
                    <div className="text-lg font-medium">
                      {formatCurrency(
                        walletTotalValue,
                        locale,
                        settings.general.defaultCurrency,
                      )}
                    </div>

                    {hasAssets ? (
                      <div className="space-y-4">
                        {nativeAssets.length > 0 && (
                          <div className="space-y-2">
                            {nativeAssets.map(assetView => {
                              const assetSymbol =
                                assetView.symbol || assetView.displayName || ""
                              const amountText =
                                assetView.asset.amount != null
                                  ? `${assetView.asset.amount.toLocaleString(locale)} ${assetSymbol}`
                                  : assetSymbol
                              const color =
                                chartColorMap.get(assetView.groupingKey) ??
                                "transparent"
                              const hasAccent = color !== "transparent"
                              const isHighlighted =
                                highlightedAsset === assetView.groupingKey

                              return (
                                <div
                                  key={assetView.asset.id}
                                  ref={element =>
                                    registerAssetRef(
                                      assetView.groupingKey,
                                      element,
                                    )
                                  }
                                  className={`rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 p-3 ${
                                    hasAccent ? "border-l-[6px]" : ""
                                  } ${
                                    isHighlighted
                                      ? "border-primary/60 dark:border-primary/60 bg-primary/10 dark:bg-primary/20"
                                      : ""
                                  }`}
                                  style={
                                    hasAccent
                                      ? {
                                          borderLeftColor: color,
                                          borderLeftWidth: 6,
                                        }
                                      : undefined
                                  }
                                >
                                  <div className="flex items-center justify-between gap-3">
                                    <div className="flex items-center gap-3 min-w-0">
                                      <div className="relative w-8 h-8 flex-shrink-0">
                                        {assetView.iconUrl && (
                                          <img
                                            src={assetView.iconUrl}
                                            alt={assetView.displayName}
                                            className="h-full w-full object-contain"
                                            onError={event => {
                                              event.currentTarget.classList.add(
                                                "hidden",
                                              )
                                              const fallback =
                                                event.currentTarget
                                                  .nextElementSibling
                                              if (
                                                fallback instanceof HTMLElement
                                              ) {
                                                fallback.classList.remove(
                                                  "hidden",
                                                )
                                              }
                                            }}
                                          />
                                        )}
                                        <div
                                          className={`absolute inset-0 flex items-center justify-center rounded-full bg-gray-300 dark:bg-gray-600 ${
                                            assetView.iconUrl ? "hidden" : ""
                                          }`}
                                        >
                                          <span className="text-gray-700 dark:text-gray-300 text-sm font-bold">
                                            {assetSymbol
                                              .slice(0, 2)
                                              .toUpperCase()}
                                          </span>
                                        </div>
                                      </div>
                                      <div className="min-w-0">
                                        <p
                                          className="font-medium truncate"
                                          title={assetView.displayName}
                                        >
                                          {assetView.displayName}
                                        </p>
                                        <p
                                          className="text-sm text-gray-600 dark:text-gray-400 truncate"
                                          title={amountText}
                                        >
                                          {amountText}
                                        </p>
                                      </div>
                                    </div>
                                    <div className="text-right">
                                      <p className="font-medium">
                                        {assetView.valueAvailable
                                          ? formatCurrency(
                                              assetView.value,
                                              locale,
                                              settings.general.defaultCurrency,
                                            )
                                          : t.common.notAvailable}
                                      </p>
                                      {assetView.roi !== null && (
                                        <div
                                          className={`flex items-center gap-1 text-sm ${
                                            assetView.roi >= 0
                                              ? "text-green-600 dark:text-green-400"
                                              : "text-red-600 dark:text-red-400"
                                          }`}
                                        >
                                          {assetView.roi >= 0 ? (
                                            <TrendingUp className="h-3 w-3" />
                                          ) : (
                                            <TrendingDown className="h-3 w-3" />
                                          )}
                                          <span>
                                            {`${assetView.roi >= 0 ? "+" : "-"}${formatPercentage(
                                              Math.abs(assetView.roi),
                                              locale,
                                            )}`}
                                          </span>
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              )
                            })}
                          </div>
                        )}

                        {tokenAssets.length > 0 && (
                          <div className="space-y-2">
                            <div className="flex items-center justify-between">
                              <h5 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                                {t.walletManagement.tokens} (
                                {tokenAssets.length})
                              </h5>
                              <Button
                                variant="link"
                                size="sm"
                                className="h-auto px-0 text-xs"
                                onClick={() => handleViewAllTokens(wallet)}
                                type="button"
                              >
                                {t.walletManagement.viewAllTokens}
                              </Button>
                            </div>
                            <div className="space-y-2 max-h-40 overflow-y-auto">
                              {tokenAssets.map(assetView => {
                                const assetSymbol =
                                  assetView.symbol ||
                                  assetView.displayName ||
                                  ""
                                const amountText =
                                  assetView.asset.amount != null
                                    ? `${assetView.asset.amount.toLocaleString(locale)} ${assetSymbol}`
                                    : assetSymbol
                                const color =
                                  chartColorMap.get(assetView.groupingKey) ??
                                  "transparent"
                                const hasAccent = color !== "transparent"
                                const isHighlighted =
                                  highlightedAsset === assetView.groupingKey

                                return (
                                  <div
                                    key={assetView.asset.id}
                                    ref={element =>
                                      registerAssetRef(
                                        assetView.groupingKey,
                                        element,
                                      )
                                    }
                                    className={`flex items-center justify-between gap-3 p-2 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded ${
                                      hasAccent ? "border-l-[6px]" : ""
                                    } ${
                                      isHighlighted
                                        ? "border-primary/60 dark:border-primary/60 bg-primary/10 dark:bg-primary/20"
                                        : ""
                                    }`}
                                    style={
                                      hasAccent
                                        ? {
                                            borderLeftColor: color,
                                            borderLeftWidth: 6,
                                          }
                                        : undefined
                                    }
                                  >
                                    <div className="flex items-center gap-2 min-w-0">
                                      <div className="relative w-6 h-6 flex-shrink-0">
                                        {assetView.iconUrl && (
                                          <img
                                            src={assetView.iconUrl}
                                            alt={assetView.displayName}
                                            className="h-full w-full object-contain"
                                            onError={event => {
                                              event.currentTarget.classList.add(
                                                "hidden",
                                              )
                                              const fallback =
                                                event.currentTarget
                                                  .nextElementSibling
                                              if (
                                                fallback instanceof HTMLElement
                                              ) {
                                                fallback.classList.remove(
                                                  "hidden",
                                                )
                                              }
                                            }}
                                          />
                                        )}
                                        <div
                                          className={`absolute inset-0 flex items-center justify-center rounded-full bg-gray-300 dark:bg-gray-600 ${
                                            assetView.iconUrl ? "hidden" : ""
                                          }`}
                                        >
                                          <span className="text-gray-700 dark:text-gray-300 text-xs font-bold">
                                            {assetSymbol
                                              .slice(0, 2)
                                              .toUpperCase()}
                                          </span>
                                        </div>
                                      </div>
                                      <div className="min-w-0">
                                        <p
                                          className="text-sm font-medium truncate"
                                          title={assetView.displayName}
                                        >
                                          {assetView.displayName}
                                        </p>
                                        <p
                                          className="text-xs text-gray-600 dark:text-gray-400 truncate"
                                          title={amountText}
                                        >
                                          {amountText}
                                        </p>
                                      </div>
                                    </div>
                                    <div className="text-right">
                                      <p className="text-sm font-medium">
                                        {assetView.valueAvailable
                                          ? formatCurrency(
                                              assetView.value,
                                              locale,
                                              settings.general.defaultCurrency,
                                            )
                                          : t.common.notAvailable}
                                      </p>
                                    </div>
                                  </div>
                                )
                              })}
                            </div>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="rounded-lg border border-dashed border-gray-300 dark:border-gray-700 py-6 text-center text-sm text-gray-500 dark:text-gray-400">
                        {t.common.noDataAvailable}
                      </div>
                    )}
                  </div>
                )
              })}

            {entityGroup.wallets
              .filter(walletGroup => isWalletlessEntry(walletGroup.wallet))
              .flatMap(walletGroup => walletGroup.assets)
              .map(assetView => {
                const assetSymbol =
                  assetView.symbol || assetView.displayName || ""
                const amountText =
                  assetView.asset.amount != null
                    ? `${formatNumber(assetView.asset.amount, locale)} ${assetSymbol}`
                    : assetSymbol
                const color =
                  chartColorMap.get(assetView.groupingKey) ?? "transparent"
                const hasAccent = color !== "transparent"
                const isHighlighted = highlightedAsset === assetView.groupingKey

                return (
                  <div
                    key={
                      assetView.originalId ??
                      assetView.localId ??
                      assetView.groupingKey
                    }
                    ref={element =>
                      registerAssetRef(assetView.groupingKey, element)
                    }
                    className="self-start"
                  >
                    <Card
                      className={`overflow-hidden ${hasAccent ? "border-l-[6px]" : ""} ${
                        isHighlighted
                          ? "border-primary/60 dark:border-primary/60 bg-primary/10 dark:bg-primary/20"
                          : ""
                      }`}
                      style={
                        hasAccent
                          ? { borderLeftColor: color, borderLeftWidth: 6 }
                          : undefined
                      }
                    >
                      <CardContent className="space-y-4 pt-4">
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex items-center gap-3 min-w-0">
                            <div className="relative w-8 h-8 flex-shrink-0">
                              {assetView.iconUrl && (
                                <img
                                  src={assetView.iconUrl}
                                  alt={assetView.displayName}
                                  className="h-full w-full object-contain"
                                  onError={event => {
                                    event.currentTarget.classList.add("hidden")
                                    const fallback =
                                      event.currentTarget.nextElementSibling
                                    if (fallback instanceof HTMLElement) {
                                      fallback.classList.remove("hidden")
                                    }
                                  }}
                                />
                              )}
                              <div
                                className={`absolute inset-0 flex items-center justify-center rounded-full bg-gray-300 dark:bg-gray-600 ${
                                  assetView.iconUrl ? "hidden" : ""
                                }`}
                              >
                                <span className="text-gray-700 dark:text-gray-300 text-sm font-bold">
                                  {assetSymbol.slice(0, 2).toUpperCase()}
                                </span>
                              </div>
                            </div>
                            <div className="min-w-0 flex flex-col gap-1">
                              <p
                                className="font-medium truncate"
                                title={assetView.displayName}
                              >
                                {assetView.displayName}
                              </p>
                              <p
                                className="text-sm text-gray-600 dark:text-gray-400 truncate"
                                title={amountText}
                              >
                                {amountText}
                              </p>
                            </div>
                          </div>
                          <div className="text-right">
                            <p className="text-lg font-semibold">
                              {assetView.valueAvailable
                                ? formatCurrency(
                                    assetView.value,
                                    locale,
                                    settings.general.defaultCurrency,
                                  )
                                : t.common.notAvailable}
                            </p>
                            {assetView.roi !== null && (
                              <div
                                className={`flex items-center justify-end gap-1 text-sm ${
                                  assetView.roi >= 0
                                    ? "text-green-600 dark:text-green-400"
                                    : "text-red-600 dark:text-red-400"
                                }`}
                              >
                                {assetView.roi >= 0 ? (
                                  <TrendingUp className="h-3 w-3" />
                                ) : (
                                  <TrendingDown className="h-3 w-3" />
                                )}
                                <span>
                                  {`${assetView.roi >= 0 ? "+" : "-"}${formatPercentage(
                                    Math.abs(assetView.roi),
                                    locale,
                                  )}`}
                                </span>
                              </div>
                            )}
                          </div>
                        </div>
                        {isEditMode && assetView.isManual && (
                          <div className="flex items-center justify-end gap-2 pt-2 border-t border-gray-200 dark:border-gray-700">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => {
                                if (assetView.originalId) {
                                  editByOriginalId(assetView.originalId)
                                } else if (assetView.localId) {
                                  editByLocalId(assetView.localId)
                                }
                              }}
                            >
                              <Edit3 className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-red-500 hover:text-red-600"
                              onClick={() => {
                                if (assetView.originalId) {
                                  deleteByOriginalId(assetView.originalId)
                                } else if (assetView.localId) {
                                  deleteByLocalId(assetView.localId)
                                }
                              }}
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  </div>
                )
              })}
          </div>
        </motion.section>
      ))}
    </motion.div>
  )

  const networkView = (
    <motion.div
      key={`network-${networkGroups.length}-${networkGroups.reduce((sum, g) => sum + g.assets.length, 0)}`}
      variants={fadeListContainer}
      initial="hidden"
      animate="show"
      className="space-y-8 pb-6"
    >
      {networkGroups.map(networkGroup => (
        <motion.section
          key={networkGroup.entity.id}
          variants={fadeListItem}
          className="space-y-4"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {(networkGroup.entity.origin === "NATIVE" ||
                networkGroup.entity.icon_url) && (
                <div
                  className={`w-10 h-10 flex-shrink-0 overflow-hidden ${
                    networkGroup.entity.origin === "MANUAL"
                      ? "rounded-full"
                      : "rounded-md"
                  }`}
                >
                  <img
                    src={
                      networkGroup.entity.origin !== "NATIVE" &&
                      networkGroup.entity.icon_url
                        ? networkGroup.entity.icon_url
                        : `entities/${networkGroup.entity.id}.png`
                    }
                    alt={networkGroup.entity.name}
                    className={`h-full w-full ${
                      networkGroup.entity.origin === "MANUAL"
                        ? "object-cover"
                        : "object-contain"
                    }`}
                    onError={event => {
                      event.currentTarget.style.display = "none"
                    }}
                  />
                </div>
              )}
              <div>
                <h3 className="text-xl font-semibold">
                  {networkGroup.entity.name}
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  {networkGroup.assets.length}{" "}
                  {networkGroup.assets.length === 1
                    ? t.investments.asset
                    : t.investments.assets}
                </p>
              </div>
            </div>
            <div className="text-right">
              <div className="text-2xl font-bold">
                {formatCurrency(
                  networkGroup.totalValue,
                  locale,
                  settings.general.defaultCurrency,
                )}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">
                {t.walletManagement.totalValue}
              </div>
            </div>
          </div>

          <div className="grid gap-4 grid-cols-1 md:grid-cols-2 2xl:grid-cols-3">
            {networkGroup.assets.length === 0 ? (
              <div className="rounded-lg border border-dashed border-gray-300 dark:border-gray-700 p-6 text-center text-sm text-gray-500 dark:text-gray-400">
                {t.common.noDataAvailable}
              </div>
            ) : (
              networkGroup.assets.map(assetSummary => {
                const color =
                  chartColorMap.get(assetSummary.groupingKey) ?? "transparent"
                const hasAccent = color !== "transparent"
                const isHighlighted =
                  highlightedAsset === assetSummary.groupingKey
                const amountText = `${formatNumber(assetSummary.totalAmount, locale)} ${assetSummary.symbol}`

                return (
                  <div
                    key={assetSummary.key}
                    ref={element =>
                      registerAssetRef(assetSummary.groupingKey, element)
                    }
                  >
                    <Card
                      className={`h-full overflow-hidden ${
                        hasAccent ? "border-l-[6px]" : ""
                      } ${
                        isHighlighted
                          ? "border-primary/60 dark:border-primary/60 bg-primary/10 dark:bg-primary/20"
                          : ""
                      }`}
                      style={
                        hasAccent
                          ? { borderLeftColor: color, borderLeftWidth: 6 }
                          : undefined
                      }
                    >
                      <CardContent className="space-y-4 pt-4">
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex items-center gap-3 min-w-0">
                            <div className="relative w-8 h-8 flex-shrink-0">
                              {assetSummary.iconUrl && (
                                <img
                                  src={assetSummary.iconUrl}
                                  alt={assetSummary.displayName}
                                  className="h-full w-full object-contain"
                                  onError={event => {
                                    event.currentTarget.classList.add("hidden")
                                    const fallback =
                                      event.currentTarget.nextElementSibling
                                    if (fallback instanceof HTMLElement) {
                                      fallback.classList.remove("hidden")
                                    }
                                  }}
                                />
                              )}
                              <div
                                className={`absolute inset-0 flex items-center justify-center rounded-full bg-gray-300 dark:bg-gray-600 ${
                                  assetSummary.iconUrl ? "hidden" : ""
                                }`}
                              >
                                <span className="text-gray-700 dark:text-gray-300 text-sm font-bold">
                                  {assetSummary.symbol
                                    .slice(0, 2)
                                    .toUpperCase()}
                                </span>
                              </div>
                            </div>
                            <div className="min-w-0 flex flex-col gap-1">
                              <div className="flex items-center gap-2 min-w-0">
                                <p
                                  className="font-medium truncate"
                                  title={assetSummary.displayName}
                                >
                                  {assetSummary.displayName}
                                </p>
                                <div className="flex-shrink-0">
                                  <WalletOwnershipBadge
                                    wallets={assetSummary.wallets}
                                    label={t.investments.cryptoView.belongsTo}
                                    countLabel={
                                      assetSummary.wallets.length === 1
                                        ? t.walletManagement.wallet
                                        : t.walletManagement.wallets
                                    }
                                  />
                                </div>
                              </div>
                              <p
                                className="text-sm text-gray-600 dark:text-gray-400 truncate"
                                title={amountText}
                              >
                                {amountText}
                              </p>
                            </div>
                          </div>
                          <div className="text-right">
                            <p className="text-lg font-semibold">
                              {assetSummary.valueAvailable
                                ? formatCurrency(
                                    assetSummary.totalValue,
                                    locale,
                                    settings.general.defaultCurrency,
                                  )
                                : t.common.notAvailable}
                            </p>
                            {assetSummary.roi !== null && (
                              <div
                                className={`flex items-center gap-1 text-sm ${
                                  assetSummary.roi >= 0
                                    ? "text-green-600 dark:text-green-400"
                                    : "text-red-600 dark:text-red-400"
                                }`}
                              >
                                {assetSummary.roi >= 0 ? (
                                  <TrendingUp className="h-3 w-3" />
                                ) : (
                                  <TrendingDown className="h-3 w-3" />
                                )}
                                <span>
                                  {`${assetSummary.roi >= 0 ? "+" : "-"}${formatPercentage(
                                    Math.abs(assetSummary.roi),
                                    locale,
                                  )}`}
                                </span>
                              </div>
                            )}
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                )
              })
            )}
          </div>
        </motion.section>
      ))}
    </motion.div>
  )

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
            <ArrowLeft size={20} />
          </Button>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold">{t.common.cryptoInvestments}</h1>
            <PinAssetButton assetId="crypto" />
          </div>
        </div>
        <div className="flex items-center gap-2 self-start sm:self-auto">
          <ManualPositionsControls className="self-start sm:self-auto" />
          <Button
            variant="default"
            size="sm"
            disabled={isEditMode}
            onClick={() => {
              if (isEditMode) return
              navigate("/entities#crypto-enabled")
            }}
          >
            <Plus className="h-4 w-4 mr-2" /> {t.entities.connect}
          </Button>
        </div>
      </div>
      <ManualPositionsUnsavedNotice />

      <InvestmentFilters
        entityOptions={entityOptions}
        selectedEntities={selectedEntities}
        onEntitiesChange={setSelectedEntities}
        walletOptions={walletFilterOptions}
        selectedWallets={selectedWalletFilters}
        onWalletsChange={setSelectedWalletFilters}
      />

      {noResults ? (
        <Card className="p-14 text-center flex flex-col items-center gap-4">
          {getIconForAssetType(
            ProductType.CRYPTO,
            "h-16 w-16",
            "text-gray-400 dark:text-gray-600",
          )}
          <div className="text-gray-500 dark:text-gray-400 text-sm max-w-md">
            {hasActiveFilters
              ? t.investments.noPositionsFound.replace(
                  "{type}",
                  cryptoWalletsLabel.toLowerCase(),
                )
              : t.investments.noPositionsAvailable.replace(
                  "{type}",
                  cryptoWalletsLabel.toLowerCase(),
                )}
          </div>
        </Card>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 items-stretch">
            <div className="flex flex-col gap-4 xl:col-span-1 order-1 xl:order-1">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">
                    {t.common.cryptoInvestments}
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  <p className="text-2xl font-bold">{formattedTotalValue}</p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">
                    {t.investments.numberOfAssets}
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  <p className="text-2xl font-bold">{totalCryptoAssets}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    {totalCryptoAssets === 1
                      ? t.investments.asset
                      : t.investments.assets}
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">
                    {t.walletManagement.wallets}
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  <p className="text-2xl font-bold">{totalFilteredWallets}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    {totalFilteredWallets === 1
                      ? t.walletManagement.wallet
                      : t.walletManagement.wallets}
                  </p>
                </CardContent>
              </Card>
            </div>
            <div className="xl:col-span-2 order-2 xl:order-2 flex items-center">
              <InvestmentDistributionChart
                data={chartData}
                title={t.common.distribution}
                locale={locale}
                currency={settings.general.defaultCurrency}
                hideLegend
                containerClassName="overflow-visible w-full"
                variant="bare"
                onSliceClick={slice => {
                  const identifier = (slice as { id?: string }).id ?? slice.name
                  const ref = symbolRefs.current[identifier]
                  if (ref) {
                    ref.scrollIntoView({
                      behavior: "smooth",
                      block: "center",
                    })
                    setHighlightedAsset(identifier)
                    setTimeout(
                      () =>
                        setHighlightedAsset(prev =>
                          prev === identifier ? null : prev,
                        ),
                      1500,
                    )
                  }
                }}
              />
            </div>
          </div>

          <Tabs
            value={viewMode}
            onValueChange={value => {
              setViewMode(value as ViewMode)
            }}
            className="space-y-6"
          >
            <div className="flex justify-end">
              <div className="flex items-center gap-3">
                <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
                  {t.investments.cryptoView.viewModeLabel}
                </span>
                <TabsList>
                  <TabsTrigger value="wallets">
                    {t.investments.cryptoView.viewModes.wallets}
                  </TabsTrigger>
                  <TabsTrigger value="network">
                    {t.investments.cryptoView.viewModes.network}
                  </TabsTrigger>
                </TabsList>
              </div>
            </div>

            <TabsContent value="wallets" className="mt-0">
              <AnimatePresence mode="wait">{walletView}</AnimatePresence>
            </TabsContent>
            <TabsContent value="network" className="mt-0">
              <AnimatePresence mode="wait">{networkView}</AnimatePresence>
            </TabsContent>
          </Tabs>
        </div>
      )}

      <ConfirmationDialog
        isOpen={showDeleteConfirm}
        title={t.common.warning}
        message={t.walletManagement.deleteWalletConfirm.replace(
          "{{walletName}}",
          walletToDelete?.name || walletToDelete?.address || "",
        )}
        onConfirm={confirmDeleteWallet}
        onCancel={() => {
          setShowDeleteConfirm(false)
          setWalletToDelete(null)
          setDeleteWalletEntityId(null)
        }}
        isLoading={isDeletingWallet}
        confirmText={t.common.delete}
        cancelText={t.common.cancel}
      />

      <EditDialog
        isOpen={showEditDialog}
        title={t.walletManagement.editWalletName}
        value={editWalletName}
        onValueChange={setEditWalletName}
        onConfirm={confirmEditWallet}
        onCancel={() => {
          setShowEditDialog(false)
          setWalletToEdit(null)
          setEditWalletName("")
          setEditWalletEntityId(null)
        }}
        isLoading={isUpdatingWallet}
        placeholder={t.walletManagement.walletNamePlaceholder}
        confirmText={t.common.save}
        cancelText={t.common.cancel}
      />
    </div>
  )
}
