import { useState, useEffect, useCallback, useRef } from "react"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import { useFinancialData } from "@/context/FinancialDataContext"
import { formatCurrency } from "@/lib/formatters"
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
} from "lucide-react"
import { motion } from "framer-motion"
import type { Entity, ExchangeRates } from "@/types"
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

  const entity: Entity | undefined = entities?.find(e => e.id === entityId)

  useEffect(() => {
    if (!entity) {
      setWallets([])
      setIsLoading(false)
      return
    }

    setIsLoading(true)

    const cryptoProduct =
      positionsData?.positions[entity.id]?.products[ProductType.CRYPTO]
    const positionWallets =
      (cryptoProduct as { entries: CryptoCurrencyWallet[] })?.entries || []

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
      const addressKey = wallet.address.toLowerCase()
      const connection = connectedWallets.find(
        conn => conn.address.toLowerCase() === addressKey,
      )
      const assets = getWalletAssets(wallet, { hideUnknownTokens })
      const assetViews = assets.map(buildAssetView)
      const nativeAssets = assetViews.filter(item => !item.isToken)
      const tokenAssets = assetViews.filter(item => item.isToken)
      const totalValue = assetViews.reduce((sum, view) => sum + view.value, 0)
      const totalInitialInvestment = assetViews.reduce(
        (sum, view) => sum + view.initialInvestment,
        0,
      )
      const displayName =
        connection?.name || wallet.name || wallet.address || addressKey

      combinedWallets.push({
        wallet: { ...wallet, name: displayName },
        connectionId: connection?.id ?? null,
        displayName,
        assets: assetViews,
        nativeAssets,
        tokenAssets,
        totalValue,
        totalInitialInvestment,
      })

      seenAddresses.add(addressKey)
    })

    connectedWallets.forEach(connection => {
      const addressKey = connection.address.toLowerCase()
      if (seenAddresses.has(addressKey)) {
        return
      }

      const placeholderWallet: CryptoCurrencyWallet = {
        id: connection.id,
        address: connection.address,
        name: connection.name,
        assets: [],
      }

      combinedWallets.push({
        wallet: placeholderWallet,
        connectionId: connection.id,
        displayName: connection.name,
        assets: [],
        nativeAssets: [],
        tokenAssets: [],
        totalValue: 0,
        totalInitialInvestment: 0,
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
          entry.wallet.address.toLowerCase() ===
          walletToEdit.wallet.address.toLowerCase()
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
          entry =>
            entry.wallet.address.toLowerCase() !==
            walletToDelete.wallet.address.toLowerCase(),
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

    const fallbackCopy = (text: string) => {
      const textArea = document.createElement("textarea")
      textArea.value = text
      textArea.setAttribute("readonly", "")
      textArea.style.position = "absolute"
      textArea.style.left = "-9999px"
      document.body.appendChild(textArea)
      textArea.select()
      document.execCommand("copy")
      document.body.removeChild(textArea)
    }

    const performCopy = async () => {
      try {
        if (navigator?.clipboard?.writeText) {
          await navigator.clipboard.writeText(address)
        } else {
          fallbackCopy(address)
        }
      } catch (error) {
        console.warn("Failed to copy wallet address", error)
        fallbackCopy(address)
      } finally {
        setCopiedAddress(address)
        if (copyTimeoutRef.current) {
          clearTimeout(copyTimeoutRef.current)
        }
        copyTimeoutRef.current = setTimeout(() => {
          setCopiedAddress(prev => (prev === address ? null : prev))
        }, 1500)
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
        <p className="mt-4 text-gray-500 dark:text-gray-400">
          {t.common.loading}
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={onBack}
            className="p-1 h-8 w-8"
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h2 className="text-2xl font-bold">{t.walletManagement.title}</h2>
            <p className="text-gray-600 dark:text-gray-400">
              {t.walletManagement.subtitle.replace(
                "{{entityName}}",
                entity.name,
              )}
            </p>
          </div>
        </div>
        <Button onClick={onAddWallet} className="flex items-center gap-2">
          <Plus className="h-4 w-4" />
          {t.walletManagement.addWallet}
        </Button>
      </div>

      {wallets.length === 0 ? (
        <Card className="text-center py-12">
          <CardContent>
            <Wallet className="h-12 w-12 mx-auto text-gray-400 mb-4" />
            <h3 className="text-lg font-medium mb-2">
              {t.walletManagement.noWallets}
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mb-6">
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
          className="grid grid-cols-1 lg:grid-cols-2 gap-6"
        >
          {wallets.map(walletEntry => {
            const walletKey =
              walletEntry.wallet.id ||
              walletEntry.connectionId ||
              walletEntry.wallet.address
            const hasAssets = walletEntry.assets.length > 0
            const assetCountLabel =
              walletEntry.assets.length === 1
                ? t.investments.asset
                : t.investments.assets

            return (
              <motion.div key={walletKey} variants={item}>
                <Card
                  className={`transition-all hover:shadow-md ${
                    hasAssets ? "" : "opacity-75 border-dashed"
                  }`}
                >
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-blue-100 dark:bg-blue-900 rounded-lg">
                          <Wallet className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <CardTitle className="text-lg">
                              {walletEntry.displayName}
                            </CardTitle>
                            {!hasAssets && (
                              <span className="text-xs bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400 px-2 py-1 rounded">
                                {t.common.noDataAvailable}
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-2 group">
                            <p className="text-sm text-gray-600 dark:text-gray-400 font-mono">
                              {walletEntry.wallet.address.slice(0, 8)}...
                              {walletEntry.wallet.address.slice(-6)}
                            </p>
                            <Button
                              variant="ghost"
                              size="sm"
                              className={`p-1 h-6 w-6 opacity-70 hover:opacity-100 transition-all duration-200 ${
                                copiedAddress === walletEntry.wallet.address
                                  ? "text-green-600 dark:text-green-400"
                                  : "text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                              }`}
                              onClick={() =>
                                handleCopyAddress(walletEntry.wallet.address)
                              }
                              title={
                                copiedAddress === walletEntry.wallet.address
                                  ? t.common.copied
                                  : t.common.copy
                              }
                            >
                              {copiedAddress === walletEntry.wallet.address ? (
                                <Check className="h-3 w-3" />
                              ) : (
                                <Copy className="h-3 w-3" />
                              )}
                            </Button>
                          </div>
                        </div>
                      </div>
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="p-1 h-8 w-8"
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
                          className="p-1 h-8 w-8 text-red-600 hover:text-red-700"
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
                  <CardContent>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 p-3">
                        <p className="text-xs font-medium text-gray-600 dark:text-gray-300">
                          {t.investments.numberOfAssets}
                        </p>
                        <p className="mt-1 text-lg font-semibold">
                          {walletEntry.assets.length} {assetCountLabel}
                        </p>
                        {!hasAssets && (
                          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                            {t.common.noDataAvailable}
                          </p>
                        )}
                      </div>
                      <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 p-3">
                        <p className="text-xs font-medium text-gray-600 dark:text-gray-300">
                          {t.walletManagement.totalValue}
                        </p>
                        <p className="mt-1 text-lg font-semibold">
                          {formatCurrency(
                            walletEntry.totalValue,
                            locale,
                            settings.general.defaultCurrency,
                          )}
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
