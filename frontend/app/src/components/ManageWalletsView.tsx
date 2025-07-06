import { useState, useEffect } from "react"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import { useFinancialData } from "@/context/FinancialDataContext"
import { formatCurrency } from "@/lib/formatters"
import { calculateCryptoValue } from "@/utils/financialDataUtils"
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
  TrendingUp,
  Copy,
  Check,
} from "lucide-react"
import { motion } from "framer-motion"
import { Entity } from "@/types"
import { CryptoCurrencyWallet, ProductType } from "@/types/position"
import { deleteCryptoWallet, updateCryptoWallet } from "@/services/api"

interface ManageWalletsViewProps {
  entityId: string
  onBack: () => void
  onAddWallet: () => void
  onWalletUpdated?: () => void
  onClose?: () => void
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
  const [wallets, setWallets] = useState<CryptoCurrencyWallet[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [walletToDelete, setWalletToDelete] =
    useState<CryptoCurrencyWallet | null>(null)
  const [isDeletingWallet, setIsDeletingWallet] = useState(false)
  const [showEditDialog, setShowEditDialog] = useState(false)
  const [walletToEdit, setWalletToEdit] = useState<CryptoCurrencyWallet | null>(
    null,
  )
  const [editWalletName, setEditWalletName] = useState("")
  const [isUpdatingWallet, setIsUpdatingWallet] = useState(false)
  const [copiedAddress, setCopiedAddress] = useState<string | null>(null)

  const entity: Entity | undefined = entities.find(e => e.id === entityId)

  useEffect(() => {
    if (entity) {
      const cryptoProduct =
        positionsData?.positions[entity.id]?.products[ProductType.CRYPTO]
      const positionWallets =
        (cryptoProduct as { entries: CryptoCurrencyWallet[] })?.entries || []

      const connectedWallets = entity.connected || []

      const combinedWallets: CryptoCurrencyWallet[] = []

      positionWallets.forEach(wallet => {
        const connection = connectedWallets.find(
          conn => conn.address === wallet.address,
        )
        const walletWithConnectionName = {
          ...wallet,
          name: connection?.name || wallet.name,
        }
        combinedWallets.push(walletWithConnectionName)
      })

      connectedWallets.forEach(connection => {
        const existsInPositions = positionWallets.some(
          wallet => wallet.address === connection.address,
        )
        if (!existsInPositions) {
          const placeholderWallet: CryptoCurrencyWallet = {
            id: connection.id,
            wallet_connection_id: connection.id,
            address: connection.address,
            name: connection.name,
            symbol: "N/A",
            crypto: "N/A",
            amount: 0,
            initial_investment: null,
            average_buy_price: null,
            market_value: null,
            currency: null,
            tokens: null,
          }
          combinedWallets.push(placeholderWallet)
        }
      })

      setWallets(combinedWallets)
      setIsLoading(false)
    }
  }, [positionsData, entity])

  const getTotalWalletValue = (wallet: CryptoCurrencyWallet) => {
    let totalValue = 0

    if (wallet.amount && wallet.symbol) {
      totalValue += calculateCryptoValue(
        wallet.amount,
        wallet.symbol,
        settings.general.defaultCurrency,
        exchangeRates,
      )
    }

    if (wallet.tokens) {
      wallet.tokens.forEach(token => {
        if (token.amount && token.symbol) {
          totalValue += calculateCryptoValue(
            token.amount,
            token.symbol,
            settings.general.defaultCurrency,
            exchangeRates,
          )
        }
      })
    }

    return totalValue
  }

  const getTokenIcon = (tokenSymbol: string) => {
    return `entities/tokens/${tokenSymbol.toUpperCase()}.png`
  }

  const handleEditWallet = (wallet: CryptoCurrencyWallet) => {
    setWalletToEdit(wallet)
    setEditWalletName(wallet.name)
    setShowEditDialog(true)
  }

  const confirmEditWallet = async () => {
    if (!walletToEdit || !editWalletName.trim() || !entity) return

    const connection = entity.connected?.find(
      conn => conn.address === walletToEdit.address,
    )
    if (!connection) {
      console.error(
        "Could not find connection for wallet:",
        walletToEdit.address,
      )
      return
    }

    if (editWalletName.trim() === walletToEdit.name) {
      setShowEditDialog(false)
      setWalletToEdit(null)
      setEditWalletName("")
      return
    }

    setIsUpdatingWallet(true)
    try {
      await updateCryptoWallet({
        id: connection.id,
        name: editWalletName.trim(),
      })

      if (onWalletUpdated) {
        onWalletUpdated()
      }

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

  const handleDeleteWallet = (wallet: CryptoCurrencyWallet) => {
    setWalletToDelete(wallet)
    setShowDeleteConfirm(true)
  }

  const confirmDeleteWallet = async () => {
    if (!walletToDelete || !entity) return

    const connection = entity.connected?.find(
      conn => conn.address === walletToDelete.address,
    )
    if (!connection) {
      console.error(
        "Could not find connection for wallet:",
        walletToDelete.address,
      )
      return
    }

    setIsDeletingWallet(true)
    try {
      await deleteCryptoWallet(connection.id)

      setWallets(prevWallets =>
        prevWallets.filter(w => w.address !== walletToDelete.address),
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

  const handleCopyAddress = async (address: string) => {
    try {
      await navigator.clipboard.writeText(address)
      setCopiedAddress(address)

      setTimeout(() => {
        setCopiedAddress(null)
      }, 2000)
    } catch (error) {
      console.error("Failed to copy address:", error)
      const textArea = document.createElement("textarea")
      textArea.value = address
      document.body.appendChild(textArea)
      textArea.select()
      document.execCommand("copy")
      document.body.removeChild(textArea)

      setCopiedAddress(address)
      setTimeout(() => {
        setCopiedAddress(null)
      }, 2000)
    }
  }

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
          {wallets.map(wallet => (
            <motion.div key={wallet.id} variants={item}>
              <Card
                className={`transition-all hover:shadow-md ${wallet.market_value === null ? "opacity-75 border-dashed" : ""}`}
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
                            {wallet.name}
                          </CardTitle>
                          {wallet.market_value === null && (
                            <span className="text-xs bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400 px-2 py-1 rounded">
                              No data
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 group">
                          <p className="text-sm text-gray-600 dark:text-gray-400 font-mono">
                            {wallet.address.slice(0, 8)}...
                            {wallet.address.slice(-6)}
                          </p>
                          <Button
                            variant="ghost"
                            size="sm"
                            className={`p-1 h-6 w-6 opacity-70 hover:opacity-100 transition-all duration-200 ${
                              copiedAddress === wallet.address
                                ? "text-green-600 dark:text-green-400"
                                : "text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                            }`}
                            onClick={() => handleCopyAddress(wallet.address)}
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
                      </div>
                    </div>
                    <div className="flex gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="p-1 h-8 w-8"
                        onClick={() => handleEditWallet(wallet)}
                        disabled={isUpdatingWallet || isDeletingWallet}
                      >
                        <Edit3 className="h-3 w-3" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="p-1 h-8 w-8 text-red-600 hover:text-red-700"
                        onClick={() => handleDeleteWallet(wallet)}
                        disabled={isUpdatingWallet || isDeletingWallet}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 flex items-center justify-center">
                        <img
                          src={`entities/${entity.id}.png`}
                          alt={wallet.crypto}
                          className="w-8 h-8 object-contain"
                          onError={e => {
                            e.currentTarget.style.display = "none"
                            e.currentTarget.nextElementSibling?.classList.remove(
                              "hidden",
                            )
                          }}
                        />
                        <span className="hidden text-white text-xs font-bold">
                          {wallet.symbol}
                        </span>
                      </div>
                      <div>
                        <p className="font-medium">{entity.name}</p>
                        <p className="text-sm text-gray-600 dark:text-gray-400">
                          {wallet.amount > 0
                            ? `${wallet.amount.toLocaleString()} ${wallet.symbol}`
                            : "No data available"}
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      {wallet.amount && wallet.symbol ? (
                        <p className="font-medium">
                          {formatCurrency(
                            calculateCryptoValue(
                              wallet.amount,
                              wallet.symbol,
                              settings.general.defaultCurrency,
                              exchangeRates,
                            ),
                            locale,
                            settings.general.defaultCurrency,
                            settings.general.defaultCurrency,
                          )}
                        </p>
                      ) : (
                        <p className="font-medium text-gray-500">N/A</p>
                      )}
                      {wallet.initial_investment &&
                        wallet.amount &&
                        wallet.symbol && (
                          <div className="flex items-center gap-1 text-sm">
                            <TrendingUp className="h-3 w-3" />
                            <span
                              className={
                                calculateCryptoValue(
                                  wallet.amount,
                                  wallet.symbol,
                                  settings.general.defaultCurrency,
                                  exchangeRates,
                                ) >= wallet.initial_investment
                                  ? "text-green-600"
                                  : "text-red-600"
                              }
                            >
                              {(
                                ((calculateCryptoValue(
                                  wallet.amount,
                                  wallet.symbol,
                                  settings.general.defaultCurrency,
                                  exchangeRates,
                                ) -
                                  wallet.initial_investment) /
                                  wallet.initial_investment) *
                                100
                              ).toFixed(1)}
                              %
                            </span>
                          </div>
                        )}
                    </div>
                  </div>

                  {wallet.tokens && wallet.tokens.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                        {t.walletManagement.tokens} ({wallet.tokens.length})
                      </h4>
                      <div className="space-y-2 max-h-40 overflow-y-auto">
                        {wallet.tokens.map(token => (
                          <div
                            key={token.id}
                            className="flex items-center justify-between p-2 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded"
                          >
                            <div className="flex items-center gap-2">
                              <div className="w-6 h-6 flex items-center justify-center">
                                <img
                                  src={getTokenIcon(token.token)}
                                  alt={token.symbol}
                                  className="w-6 h-6 object-contain"
                                  onError={e => {
                                    e.currentTarget.style.display = "none"
                                    const parent = e.currentTarget.parentElement
                                    if (parent) {
                                      parent.innerHTML = `<div class="w-6 h-6 rounded-full bg-gray-300 dark:bg-gray-600 flex items-center justify-center"><span class="text-gray-700 dark:text-gray-300 text-xs font-bold">${token.symbol.slice(0, 2)}</span></div>`
                                    }
                                  }}
                                />
                              </div>
                              <div>
                                <p className="text-sm font-medium">
                                  {token.name}
                                </p>
                                <p className="text-xs text-gray-600 dark:text-gray-400">
                                  {token.amount.toLocaleString()} {token.symbol}
                                </p>
                              </div>
                            </div>
                            <div className="text-right">
                              {token.amount && token.symbol && (
                                <p className="text-sm font-medium">
                                  {formatCurrency(
                                    calculateCryptoValue(
                                      token.amount,
                                      token.symbol,
                                      settings.general.defaultCurrency,
                                      exchangeRates,
                                    ),
                                    locale,
                                    settings.general.defaultCurrency,
                                    settings.general.defaultCurrency,
                                  )}
                                </p>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="border-t pt-3">
                    <div className="flex items-center justify-between">
                      <span className="font-medium">
                        {t.walletManagement.totalValue}
                      </span>
                      <span className="text-lg font-bold">
                        {wallet.market_value !== null
                          ? formatCurrency(
                              getTotalWalletValue(wallet),
                              locale,
                              settings.general.defaultCurrency,
                            )
                          : "N/A"}
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </motion.div>
      )}

      <ConfirmationDialog
        isOpen={showDeleteConfirm}
        title={t.common.warning}
        message={t.walletManagement.deleteWalletConfirm.replace(
          "{{walletName}}",
          walletToDelete?.name || "",
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
