import { useState, useEffect, useCallback, useRef } from "react"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import { useFinancialData } from "@/context/FinancialDataContext"
import { formatCurrency } from "@/lib/formatters"
import { Sensitive } from "@/components/ui/Sensitive"
import { copyToClipboard } from "@/lib/clipboard"
import {
  calculateCryptoAssetInitialInvestment,
  calculateCryptoAssetValue,
  getWalletAssets,
} from "@/utils/financialDataUtils"
import { Button } from "@/components/ui/Button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { ConfirmationDialog } from "@/components/ui/ConfirmationDialog"
import { EditDialog } from "@/components/ui/EditDialog"
import {
  ArrowLeft,
  Plus,
  Trash2,
  Edit3,
  Wallet,
  Copy,
  Check,
  Key,
} from "lucide-react"
import { motion } from "framer-motion"
import type { Entity, ExchangeRates, CryptoWalletConnection } from "@/types"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import {
  CryptoCurrencyWallet,
  ProductType,
  CryptoCurrencyPosition,
  CryptoCurrencyType,
} from "@/types/position"
import { deleteCryptoWallet, updateCryptoWallet } from "@/services/api"

interface ManageWalletsViewProps {
  entityId: string
  onBack: () => void
  onAddWallet: () => void
  onWalletUpdated?: () => void
  onClose?: () => void
}

interface WalletAssetView {
  asset: CryptoCurrencyPosition
  symbol: string
  displayName: string
  value: number
  initialInvestment: number
  roi: number | null
  amount: number
  isToken: boolean
  iconUrl: string | null
}

interface WalletEntry {
  wallet: CryptoCurrencyWallet
  connectionId: string | null
  connection: CryptoWalletConnection | null
  displayName: string
  assets: WalletAssetView[]
  nativeAssets: WalletAssetView[]
  tokenAssets: WalletAssetView[]
  totalValue: number
  totalInitialInvestment: number
}

export function ManageWalletsView({
  entityId,
  onBack,
  onAddWallet,
  onWalletUpdated,
  onClose,
}: ManageWalletsViewProps) {
  const { t, locale } = useI18n()
  const { entities, settings, exchangeRates } = useAppContext()
  const { positionsData } = useFinancialData()
  const [wallets, setWallets] = useState<WalletEntry[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [walletToDelete, setWalletToDelete] = useState<WalletEntry | null>(null)
  const [isDeletingWallet, setIsDeletingWallet] = useState(false)
  const [showEditDialog, setShowEditDialog] = useState(false)
  const [walletToEdit, setWalletToEdit] = useState<WalletEntry | null>(null)
  const [editWalletName, setEditWalletName] = useState("")
  const [isUpdatingWallet, setIsUpdatingWallet] = useState(false)
  const [copiedAddress, setCopiedAddress] = useState<string | null>(null)
  const copyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const getWalletAddresses = (
    wallet: CryptoCurrencyWallet | null | undefined,
  ): string[] => {
    return (wallet?.addresses ?? []).filter(Boolean)
  }

  const getPrimaryAddress = (
    wallet: CryptoCurrencyWallet | null | undefined,
  ): string | null => {
    const addresses = getWalletAddresses(wallet)
    return addresses.length > 0 ? addresses[0] : null
  }

  const entity: Entity | undefined = entities?.find(e => e.id === entityId)

  useEffect(() => {
    if (!entity) {
      setWallets([])
      setIsLoading(false)
      return
    }

    setIsLoading(true)

    const entityPositions = positionsData?.positions[entity.id] ?? []
    const positionWallets = entityPositions.flatMap(pos => {
      const cryptoProduct = pos.products[ProductType.CRYPTO]
      return cryptoProduct && "entries" in cryptoProduct
        ? (cryptoProduct.entries as CryptoCurrencyWallet[])
        : []
    })

    const connectedWallets = entity.connected || []
    const combinedWallets: WalletEntry[] = []
    const seenAddresses = new Set<string>()
    const rates = (exchangeRates ?? {}) as ExchangeRates
    const targetCurrency = settings.general.defaultCurrency
    const entityIconPath = `entities/${entity.id}.png`
    const hideUnknownTokens =
      settings.assets?.crypto?.hideUnknownTokens ?? false

    const buildAssetView = (asset: CryptoCurrencyPosition): WalletAssetView => {
      const normalizedSymbol = (
        asset.symbol ||
        asset.crypto_asset?.symbol ||
        ""
      ).toUpperCase()
      const displayName =
        asset.crypto_asset?.name || asset.name || normalizedSymbol || asset.id
      const hasAssetDetails = Boolean(asset.crypto_asset)
      const value = hasAssetDetails
        ? calculateCryptoAssetValue(asset, targetCurrency, rates)
        : 0
      const initialInvestment = hasAssetDetails
        ? calculateCryptoAssetInitialInvestment(asset, targetCurrency, rates)
        : 0
      const roi =
        initialInvestment > 0
          ? ((value - initialInvestment) / initialInvestment) * 100
          : null
      const isToken =
        (asset.type ?? CryptoCurrencyType.NATIVE) ===
          CryptoCurrencyType.TOKEN || Boolean(asset.contract_address)
      const iconUrl = isToken
        ? (asset.crypto_asset?.icon_urls?.[0] ?? null)
        : entityIconPath

      return {
        asset,
        symbol: normalizedSymbol || displayName,
        displayName,
        value,
        initialInvestment,
        roi,
        amount: asset.amount ?? 0,
        isToken,
        iconUrl,
      }
    }

    positionWallets.forEach(wallet => {
      const walletAddresses = getWalletAddresses(wallet)
      const normalizedWalletAddresses = walletAddresses.map(address =>
        address.trim().toLowerCase(),
      )
      const walletXpub = wallet.hd_wallet?.xpub?.trim().toLowerCase()
      const connection = connectedWallets.find(conn => {
        if (wallet.id && conn.id === wallet.id) {
          return true
        }

        const connectionXpub = conn.hd_wallet?.xpub?.trim().toLowerCase()
        if (walletXpub && connectionXpub && walletXpub === connectionXpub) {
          return true
        }

        if (normalizedWalletAddresses.length === 0) {
          return false
        }

        const connectionAddresses = conn.addresses ?? []
        return connectionAddresses.some(address =>
          normalizedWalletAddresses.includes(address.trim().toLowerCase()),
        )
      })

      if (!connection) {
        return
      }

      const assets = getWalletAssets(wallet, { hideUnknownTokens })
      const assetViews = assets.map(buildAssetView)
      const nativeAssets = assetViews.filter(item => !item.isToken)
      const tokenAssets = assetViews.filter(item => item.isToken)
      const totalValue = assetViews.reduce((sum, view) => sum + view.value, 0)
      const totalInitialInvestment = assetViews.reduce(
        (sum, view) => sum + view.initialInvestment,
        0,
      )
      const primaryAddress = getPrimaryAddress(wallet)
      const displayName =
        connection?.name ||
        wallet.name ||
        wallet.hd_wallet?.xpub ||
        primaryAddress ||
        ""

      combinedWallets.push({
        wallet: { ...wallet, name: displayName },
        connectionId: connection.id,
        connection,
        displayName,
        assets: assetViews,
        nativeAssets,
        tokenAssets,
        totalValue,
        totalInitialInvestment,
      })

      normalizedWalletAddresses.forEach(address => {
        seenAddresses.add(address)
      })
    })

    const seenConnectionIds = new Set(
      combinedWallets.map(w => w.connectionId).filter(Boolean) as string[],
    )

    connectedWallets.forEach(connection => {
      if (seenConnectionIds.has(connection.id)) {
        return
      }

      const connectionAddresses = connection.addresses ?? []
      const normalizedConnectionAddresses = connectionAddresses.map(address =>
        address.trim().toLowerCase(),
      )
      const alreadySeen = normalizedConnectionAddresses.some(address =>
        seenAddresses.has(address),
      )
      if (alreadySeen) {
        return
      }

      const placeholderWallet: CryptoCurrencyWallet = {
        id: connection.id,
        addresses: connectionAddresses,
        name: connection.name,
        assets: [],
        hd_wallet: connection.hd_wallet ?? null,
      }

      combinedWallets.push({
        wallet: placeholderWallet,
        connectionId: connection.id,
        connection,
        displayName: connection.name,
        assets: [],
        nativeAssets: [],
        tokenAssets: [],
        totalValue: 0,
        totalInitialInvestment: 0,
      })

      normalizedConnectionAddresses.forEach(address => {
        seenAddresses.add(address)
      })
    })

    setWallets(combinedWallets)
    setIsLoading(false)
  }, [
    entity,
    positionsData,
    exchangeRates,
    settings.general.defaultCurrency,
    settings.assets?.crypto?.hideUnknownTokens,
  ])

  const handleEditWallet = (wallet: WalletEntry) => {
    if (!wallet.connectionId) {
      console.error("Cannot edit wallet without connection", wallet.wallet)
      return
    }
    setWalletToEdit(wallet)
    setEditWalletName(wallet.displayName)
    setShowEditDialog(true)
  }

  const confirmEditWallet = async () => {
    const trimmedName = editWalletName.trim()
    if (!walletToEdit || !trimmedName || !walletToEdit.connectionId) {
      return
    }

    if (trimmedName === walletToEdit.displayName) {
      setShowEditDialog(false)
      setWalletToEdit(null)
      setEditWalletName("")
      return
    }

    setIsUpdatingWallet(true)
    try {
      await updateCryptoWallet({
        id: walletToEdit.connectionId,
        name: trimmedName,
      })

      if (onWalletUpdated) {
        onWalletUpdated()
      }

      setWallets(prevWallets =>
        prevWallets.map(entry =>
          entry.connectionId === walletToEdit.connectionId
            ? {
                ...entry,
                wallet: { ...entry.wallet, name: trimmedName },
                displayName: trimmedName,
              }
            : entry,
        ),
      )

      setShowEditDialog(false)
      setWalletToEdit(null)
      setEditWalletName("")
    } catch (error) {
      console.error("Error updating wallet:", error)
    } finally {
      setIsUpdatingWallet(false)
    }
  }

  const cancelEditWallet = () => {
    setShowEditDialog(false)
    setWalletToEdit(null)
    setEditWalletName("")
  }

  const handleDeleteWallet = (wallet: WalletEntry) => {
    if (!wallet.connectionId) {
      console.error("Cannot delete wallet without connection", wallet.wallet)
      return
    }
    setWalletToDelete(wallet)
    setShowDeleteConfirm(true)
  }

  const confirmDeleteWallet = async () => {
    if (!walletToDelete?.connectionId) {
      return
    }

    setIsDeletingWallet(true)
    try {
      await deleteCryptoWallet(walletToDelete.connectionId)

      setWallets(prevWallets =>
        prevWallets.filter(
          entry => entry.connectionId !== walletToDelete.connectionId,
        ),
      )

      if (onWalletUpdated) {
        onWalletUpdated()
      }

      setShowDeleteConfirm(false)
      setWalletToDelete(null)

      if (onClose) {
        onClose()
      }
    } catch (error) {
      console.error("Error deleting wallet:", error)
    } finally {
      setIsDeletingWallet(false)
    }
  }

  const cancelDeleteWallet = () => {
    setShowDeleteConfirm(false)
    setWalletToDelete(null)
  }

  const handleCopyAddress = useCallback((address: string) => {
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
  }, [])

  useEffect(() => {
    return () => {
      if (copyTimeoutRef.current) {
        clearTimeout(copyTimeoutRef.current)
      }
    }
  }, [])

  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
      },
    },
  }

  const item = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0 },
  }

  if (isLoading || !entity) {
    return (
      <div className="flex flex-col items-center justify-center h-64">
        <LoadingSpinner size="lg" />
        <p className="mt-4 text-muted-foreground">{t.common.loading}</p>
      </div>
    )
  }

  return (
    <div className="space-y-4 sm:space-y-6">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 sm:gap-3 min-w-0">
          <Button
            variant="ghost"
            size="sm"
            onClick={onBack}
            className="p-1 h-8 w-8 flex-shrink-0"
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div className="min-w-0">
            <h2 className="text-lg sm:text-2xl font-bold truncate">
              {t.walletManagement.title}
            </h2>
            <p className="text-xs sm:text-sm text-muted-foreground truncate">
              {t.walletManagement.subtitle.replace(
                "{{entityName}}",
                entity.name,
              )}
            </p>
          </div>
        </div>
        <Button
          onClick={onAddWallet}
          size="sm"
          className="flex-shrink-0 h-8 w-8 p-0 sm:h-9 sm:w-auto sm:px-3 sm:gap-2"
        >
          <Plus className="h-4 w-4" />
          <span className="hidden sm:inline">
            {t.walletManagement.addWallet}
          </span>
        </Button>
      </div>

      {wallets.length === 0 ? (
        <Card className="text-center py-8 sm:py-12">
          <CardContent>
            <Wallet className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium mb-2">
              {t.walletManagement.noWallets}
            </h3>
            <p className="text-muted-foreground mb-6">
              {t.walletManagement.noWalletsDescription}
            </p>
            <Button
              onClick={onAddWallet}
              className="flex items-center gap-2 mx-auto"
            >
              <Plus className="h-4 w-4" />
              {t.walletManagement.addFirstWallet}
            </Button>
          </CardContent>
        </Card>
      ) : (
        <motion.div
          variants={container}
          initial="hidden"
          animate="show"
          className="grid grid-cols-1 lg:grid-cols-2 gap-3 sm:gap-6"
        >
          {wallets.map(walletEntry => {
            const primaryAddress = getPrimaryAddress(walletEntry.wallet)
            const walletAddresses = getWalletAddresses(walletEntry.wallet)
            const extraAddressCount =
              walletAddresses.length > 1 ? walletAddresses.length - 1 : 0
            const walletKey =
              walletEntry.wallet.id ||
              walletEntry.connectionId ||
              primaryAddress
            const hasAssets = walletEntry.assets.length > 0
            const assetCountLabel =
              walletEntry.assets.length === 1
                ? t.investments.asset
                : t.investments.assets
            const hdWallet =
              walletEntry.connection?.hd_wallet ?? walletEntry.wallet.hd_wallet
            const isDerived =
              walletEntry.connection?.address_source === "DERIVED" ||
              Boolean(hdWallet?.xpub)

            return (
              <motion.div key={walletKey} variants={item}>
                <Card
                  className={`transition-all hover:shadow-md ${
                    hasAssets ? "" : "opacity-75 border-dashed"
                  }`}
                >
                  <CardHeader className="p-3 sm:p-6 pb-2 sm:pb-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2 sm:gap-3 min-w-0 flex-1">
                        <div
                          className={`p-1.5 sm:p-2 rounded-lg flex-shrink-0 ${isDerived ? "bg-amber-100 dark:bg-amber-900/30" : "bg-primary/10"}`}
                        >
                          {isDerived ? (
                            <Key className="h-4 w-4 sm:h-5 sm:w-5 text-amber-600 dark:text-amber-400" />
                          ) : (
                            <Wallet className="h-4 w-4 sm:h-5 sm:w-5 text-primary" />
                          )}
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 min-w-0">
                            <CardTitle className="text-sm sm:text-lg truncate">
                              {walletEntry.displayName}
                            </CardTitle>
                            {!hasAssets && (
                              <span className="text-xs bg-secondary text-muted-foreground px-2 py-0.5 rounded flex-shrink-0">
                                {t.common.noDataAvailable}
                              </span>
                            )}
                          </div>
                          {isDerived && hdWallet ? (
                            <div className="flex items-center gap-2 group">
                              <p className="text-xs sm:text-sm text-muted-foreground font-mono truncate">
                                {hdWallet.xpub.slice(0, 12)}...
                                {hdWallet.xpub.slice(-6)}
                              </p>
                              <Button
                                variant="ghost"
                                size="sm"
                                className={`p-1 h-6 w-6 opacity-70 hover:opacity-100 transition-all duration-200 flex-shrink-0 ${
                                  copiedAddress === hdWallet.xpub
                                    ? "text-green-600 dark:text-green-400"
                                    : "text-muted-foreground"
                                }`}
                                onClick={() => handleCopyAddress(hdWallet.xpub)}
                                title={
                                  copiedAddress === hdWallet.xpub
                                    ? t.common.copied
                                    : t.common.copy
                                }
                              >
                                {copiedAddress === hdWallet.xpub ? (
                                  <Check className="h-3 w-3" />
                                ) : (
                                  <Copy className="h-3 w-3" />
                                )}
                              </Button>
                            </div>
                          ) : primaryAddress ? (
                            <div className="flex items-center gap-1.5 sm:gap-2 group">
                              <p className="text-xs sm:text-sm text-muted-foreground font-mono">
                                {primaryAddress.slice(0, 8)}...
                                {primaryAddress.slice(-6)}
                              </p>
                              {extraAddressCount > 0 && (
                                <Popover>
                                  <PopoverTrigger asChild>
                                    <button
                                      type="button"
                                      className="text-xs rounded-full border px-2 py-0.5 text-muted-foreground hover:bg-secondary"
                                    >
                                      +{extraAddressCount}
                                    </button>
                                  </PopoverTrigger>
                                  <PopoverContent
                                    align="start"
                                    sideOffset={8}
                                    className="w-72 space-y-2 p-3"
                                  >
                                    <ul className="space-y-2">
                                      {walletAddresses.map(address => (
                                        <li
                                          key={address}
                                          className="flex items-center justify-between gap-2"
                                        >
                                          <span className="text-xs font-mono text-muted-foreground break-all">
                                            {address}
                                          </span>
                                          <Button
                                            variant="ghost"
                                            size="sm"
                                            className={`p-1 h-6 w-6 flex-shrink-0 ${
                                              copiedAddress === address
                                                ? "text-green-600 dark:text-green-400"
                                                : "text-muted-foreground"
                                            }`}
                                            onClick={() =>
                                              handleCopyAddress(address)
                                            }
                                            title={
                                              copiedAddress === address
                                                ? t.common.copied
                                                : t.common.copy
                                            }
                                          >
                                            {copiedAddress === address ? (
                                              <Check className="h-3 w-3" />
                                            ) : (
                                              <Copy className="h-3 w-3" />
                                            )}
                                          </Button>
                                        </li>
                                      ))}
                                    </ul>
                                  </PopoverContent>
                                </Popover>
                              )}
                              <Button
                                variant="ghost"
                                size="sm"
                                className={`p-1 h-6 w-6 opacity-70 hover:opacity-100 transition-all duration-200 flex-shrink-0 ${
                                  copiedAddress === primaryAddress
                                    ? "text-green-600 dark:text-green-400"
                                    : "text-muted-foreground"
                                }`}
                                onClick={() =>
                                  handleCopyAddress(primaryAddress)
                                }
                                title={
                                  copiedAddress === primaryAddress
                                    ? t.common.copied
                                    : t.common.copy
                                }
                              >
                                {copiedAddress === primaryAddress ? (
                                  <Check className="h-3 w-3" />
                                ) : (
                                  <Copy className="h-3 w-3" />
                                )}
                              </Button>
                            </div>
                          ) : null}
                        </div>
                      </div>
                      <div className="flex gap-0.5 flex-shrink-0">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="p-1 h-7 w-7 sm:h-8 sm:w-8"
                          onClick={() => handleEditWallet(walletEntry)}
                          disabled={
                            isUpdatingWallet ||
                            isDeletingWallet ||
                            !walletEntry.connectionId
                          }
                        >
                          <Edit3 className="h-3 w-3" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="p-1 h-7 w-7 sm:h-8 sm:w-8 text-destructive hover:text-destructive"
                          onClick={() => handleDeleteWallet(walletEntry)}
                          disabled={
                            isUpdatingWallet ||
                            isDeletingWallet ||
                            !walletEntry.connectionId
                          }
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="p-3 pt-0 sm:p-6 sm:pt-0">
                    <div className="grid grid-cols-2 gap-2 sm:gap-3">
                      <div className="rounded-lg border bg-secondary/50 p-2 sm:p-3">
                        <p className="text-xs font-medium text-muted-foreground">
                          {t.investments.numberOfAssets}
                        </p>
                        <p className="mt-1 text-base sm:text-lg font-semibold">
                          {walletEntry.assets.length} {assetCountLabel}
                        </p>
                        {!hasAssets && (
                          <p className="mt-1 text-xs text-muted-foreground">
                            {t.common.noDataAvailable}
                          </p>
                        )}
                      </div>
                      <div className="rounded-lg border bg-secondary/50 p-2 sm:p-3">
                        <p className="text-xs font-medium text-muted-foreground">
                          {t.walletManagement.totalValue}
                        </p>
                        <p className="mt-1 text-base sm:text-lg font-semibold">
                          <Sensitive>
                            {formatCurrency(
                              walletEntry.totalValue,
                              locale,
                              settings.general.defaultCurrency,
                            )}
                          </Sensitive>
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            )
          })}
        </motion.div>
      )}

      <ConfirmationDialog
        isOpen={showDeleteConfirm}
        title={t.common.warning}
        message={t.walletManagement.deleteWalletConfirm.replace(
          "{{walletName}}",
          walletToDelete?.displayName || "",
        )}
        confirmText={t.common.delete}
        cancelText={t.common.cancel}
        onConfirm={confirmDeleteWallet}
        onCancel={cancelDeleteWallet}
        isLoading={isDeletingWallet}
      />

      <EditDialog
        isOpen={showEditDialog}
        title={t.walletManagement.editWalletName}
        value={editWalletName}
        onValueChange={setEditWalletName}
        confirmText={t.common.save}
        cancelText={t.common.cancel}
        onConfirm={confirmEditWallet}
        onCancel={cancelEditWallet}
        isLoading={isUpdatingWallet}
        placeholder={t.walletManagement.walletNamePlaceholder}
      />
    </div>
  )
}
