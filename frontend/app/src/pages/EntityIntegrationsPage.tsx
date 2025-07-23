import { useAppContext } from "@/context/AppContext"
import { EntityCard } from "@/components/EntityCard"
import { LoginForm } from "@/components/LoginForm"
import { AddWalletForm } from "@/components/AddWalletForm"
import { ManageWalletsView } from "@/components/ManageWalletsView"
import { ManageCommoditiesView } from "@/components/ManageCommoditiesView"
import { PinPad } from "@/components/PinPad"
import { FeatureSelector } from "@/components/FeatureSelector"
import { Button } from "@/components/ui/Button"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { useI18n } from "@/i18n"
import { motion, AnimatePresence } from "framer-motion"
import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import {
  RefreshCw,
  ExternalLink,
  FileSpreadsheet,
  Landmark,
  Wallet,
  User,
  Settings,
  Download,
} from "lucide-react"
import {
  EntitySetupLoginType,
  EntityStatus,
  EntityType,
  VirtualFetchError,
} from "@/types"
import { ConfirmationDialog } from "@/components/ui/ConfirmationDialog"
import { ErrorDetailsDialog } from "@/components/ui/ErrorDetailsDialog"
import { createCryptoWallet } from "@/services/api"
import { useFinancialData } from "@/context/FinancialDataContext"
import { ProductType } from "@/types/position"
import { CommodityIconsStack } from "@/utils/commodityIcons"

export default function EntityIntegrationsPage() {
  const {
    entities,
    isLoading,
    selectedEntity,
    pinRequired,
    selectEntity,
    fetchEntities,
    scrape,
    runVirtualScrape,
    view,
    setView,
    startExternalLogin,
    externalLoginInProgress,
    disconnectEntity,
    settings,
  } = useAppContext()

  const { positionsData } = useFinancialData()
  const { t } = useI18n()
  const navigate = useNavigate()
  const [showVirtualConfirm, setShowVirtualConfirm] = useState(false)
  const [isVirtualScraping, setIsVirtualScraping] = useState(false)
  const [showAddWallet, setShowAddWallet] = useState(false)
  const [isAddingWallet, setIsAddingWallet] = useState(false)
  const [showManageWallets, setShowManageWallets] = useState(false)
  const [showManageCommodities, setShowManageCommodities] = useState(false)
  const [virtualErrors, setVirtualErrors] = useState<
    VirtualFetchError[] | null
  >(null)
  const [showErrorDetails, setShowErrorDetails] = useState(false)

  const virtualEnabled = settings?.fetch?.virtual?.enabled ?? false

  // Helper function to determine if a crypto wallet entity is connected
  const isCryptoWalletConnected = (entity: any) => {
    return (
      entity.type === EntityType.CRYPTO_WALLET &&
      entity.connected &&
      entity.connected.length > 0
    )
  }

  // Helper function to determine if an entity is connected
  const isEntityConnected = (entity: any) => {
    if (entity.type === EntityType.CRYPTO_WALLET) {
      return isCryptoWalletConnected(entity)
    }
    return (
      entity.status === EntityStatus.CONNECTED ||
      entity.status === EntityStatus.REQUIRES_LOGIN
    )
  }

  // Helper function to determine if an entity is disconnected
  const isEntityDisconnected = (entity: any) => {
    if (entity.type === EntityType.CRYPTO_WALLET) {
      return !isCryptoWalletConnected(entity)
    }
    return entity.status === EntityStatus.DISCONNECTED
  }

  // Helper function to determine if commodity data entry is available
  const isCommodityDataEntryAvailable = () => {
    // Check if there are any commodity positions in the financial data
    // (commodities are positions within entities, not separate entities)
    if (!positionsData?.positions) {
      return false
    }

    // Look through all positions to find any that have commodity data
    const hasAnyCommodityPositions = Object.values(
      positionsData.positions,
    ).some(entityPosition => {
      if (entityPosition?.products[ProductType.COMMODITY]) {
        const commodityProduct = entityPosition.products[ProductType.COMMODITY]
        return (
          "entries" in commodityProduct && commodityProduct.entries.length > 0
        )
      }
      return false
    })

    return hasAnyCommodityPositions
  }

  const connectedEntities =
    entities?.filter(
      entity => isEntityConnected(entity) && entity.is_real !== false,
    ) || []

  const unconnectedEntities =
    entities?.filter(
      entity => isEntityDisconnected(entity) && entity.is_real !== false,
    ) || []

  // Categorize connected entities by type
  const connectedFinancialEntities = connectedEntities.filter(
    entity => entity.type === EntityType.FINANCIAL_INSTITUTION,
  )
  const connectedCryptoEntities = connectedEntities.filter(
    entity => entity.type === EntityType.CRYPTO_WALLET,
  )

  // Categorize unconnected entities by type
  const unconnectedFinancialEntities = unconnectedEntities.filter(
    entity => entity.type === EntityType.FINANCIAL_INSTITUTION,
  )
  const unconnectedCryptoEntities = unconnectedEntities.filter(
    entity => entity.type === EntityType.CRYPTO_WALLET,
  )

  const handleEntitySelect = (entity: any) => {
    selectEntity(entity)

    if (!entity.is_real) {
      setShowVirtualConfirm(true)
    } else if (entity.type === EntityType.CRYPTO_WALLET) {
      // For crypto wallets, if connected go to features, if not connected show add wallet form
      if (isCryptoWalletConnected(entity)) {
        setView("features")
      } else {
        setShowAddWallet(true)
      }
    } else if (entity.status === EntityStatus.DISCONNECTED) {
      handleLogin(entity)
    } else if (entity.status === EntityStatus.REQUIRES_LOGIN) {
      handleLogin(entity)
    } else {
      setView("features")
    }
  }

  const handleRelogin = (entity: any) => {
    // Only handle relogin for financial institutions
    if (entity.type === EntityType.FINANCIAL_INSTITUTION) {
      selectEntity(entity)
      handleLogin(entity)
    }
  }

  const handleDisconnect = async (entity: any) => {
    // Only handle disconnect for financial institutions
    if (entity.type === EntityType.FINANCIAL_INSTITUTION) {
      await disconnectEntity(entity.id)
    }
  }

  const handleLogin = (entity: any) => {
    if (entity.setup_login_type === EntitySetupLoginType.MANUAL) {
      setTimeout(() => {
        startExternalLogin(entity)
      }, 100)
    } else {
      setView("login")
    }
  }

  const handleVirtualConfirm = async () => {
    let result
    try {
      setIsVirtualScraping(true)
      result = await runVirtualScrape()
    } catch (error) {
      console.error("Error running virtual scrape:", error)
    } finally {
      setIsVirtualScraping(false)
      setShowVirtualConfirm(false)
    }

    if (result) {
      const { gotData, errors } = result
      if (errors && errors.length > 0) {
        setVirtualErrors(errors)
        setShowErrorDetails(true)
      }
      if (gotData) {
        await fetchEntities()
      }
    }
  }

  const handleVirtualCancel = () => {
    setShowVirtualConfirm(false)
  }

  const handleCloseErrorDetails = () => {
    setShowErrorDetails(false)
    setVirtualErrors(null)
  }

  const handleManage = (entity: any) => {
    // Only handle manage for crypto wallets
    if (
      entity.type === EntityType.CRYPTO_WALLET &&
      isCryptoWalletConnected(entity)
    ) {
      selectEntity(entity)
      setShowManageWallets(true)
    }
  }

  const handleBack = () => {
    setView("entities")
    setShowAddWallet(false)
    setShowManageWallets(false)
  }

  const handleAddWallet = async (name: string, address: string) => {
    if (!selectedEntity) return

    setIsAddingWallet(true)
    try {
      await createCryptoWallet({
        entityId: selectedEntity.id,
        name,
        address,
      })

      await scrape(selectedEntity, selectedEntity.features)

      setShowAddWallet(false)
      setView("entities")
    } finally {
      setIsAddingWallet(false)
    }
  }

  const handleCancelAddWallet = () => {
    setShowAddWallet(false)
    setView("entities")
  }

  const handleBackFromManageWallets = () => {
    setShowManageWallets(false)
    setView("entities")
  }

  const handleBackFromManageCommodities = () => {
    setShowManageCommodities(false)
  }

  const handleAddWalletFromManage = () => {
    setShowManageWallets(false)
    setShowAddWallet(true)
  }

  const handleConfigureVirtual = () => {
    navigate("/settings?tab=scrape")
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

  return (
    <div className="space-y-6 pb-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">{t.entities.title}</h1>
        {view === "entities" && (
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="icon"
              onClick={fetchEntities}
              disabled={isLoading}
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        )}
      </div>

      <AnimatePresence mode="wait">
        {isLoading && view === "entities" ? (
          <motion.div
            key="loading"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex flex-col justify-center items-center h-64"
          >
            <LoadingSpinner size="lg" />
            <p className="mt-4 text-gray-500 dark:text-gray-400">
              {t.common.loading}
            </p>
          </motion.div>
        ) : view === "entities" ? (
          <motion.div
            key="entities"
            variants={container}
            initial="hidden"
            animate="show"
            className="space-y-8"
          >
            {(connectedEntities.length > 0 ||
              virtualEnabled ||
              isCommodityDataEntryAvailable()) && (
              <motion.div variants={item} className="space-y-6">
                <h2 className="text-xl font-semibold">
                  {t.entities.connected}
                </h2>

                {/* Financial Institutions */}
                {connectedFinancialEntities.length > 0 && (
                  <div className="space-y-3">
                    <h3 className="text-lg font-medium text-gray-700 dark:text-gray-300 flex items-center">
                      <Landmark className="h-5 w-5 mr-2" />
                      {t.entities.financialInstitutions}
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                      {connectedFinancialEntities.map(entity => (
                        <EntityCard
                          key={entity.id}
                          entity={entity}
                          onSelect={() => handleEntitySelect(entity)}
                          onRelogin={() => handleRelogin(entity)}
                          onDisconnect={() => handleDisconnect(entity)}
                          onManage={() => handleManage(entity)}
                        />
                      ))}
                    </div>
                  </div>
                )}

                {/* Crypto Wallets */}
                {connectedCryptoEntities.length > 0 && (
                  <div className="space-y-3">
                    <h3 className="text-lg font-medium text-gray-700 dark:text-gray-300 flex items-center">
                      <Wallet className="h-5 w-5 mr-2" />
                      {t.entities.cryptoWallets}
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                      {connectedCryptoEntities.map(entity => (
                        <EntityCard
                          key={entity.id}
                          entity={entity}
                          onSelect={() => handleEntitySelect(entity)}
                          onRelogin={() => handleRelogin(entity)}
                          onDisconnect={() => handleDisconnect(entity)}
                          onManage={() => handleManage(entity)}
                        />
                      ))}
                    </div>
                  </div>
                )}

                {/* User Data Section */}
                {(virtualEnabled || isCommodityDataEntryAvailable()) && (
                  <div className="space-y-3">
                    <h3 className="text-lg font-medium text-gray-700 dark:text-gray-300 flex items-center">
                      <User className="h-5 w-5 mr-2" />
                      {t.entities.manualDataEntry}
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                      {/* Virtual Data Entry - only show when enabled */}
                      {virtualEnabled && (
                        <Card className="transition-all hover:shadow-md border-l-4 border-l-green-500 flex flex-col h-full">
                          <CardHeader className="pb-2">
                            <CardTitle className="flex items-center justify-center">
                              <FileSpreadsheet className="h-5 w-5 mr-2" />
                              {t.entities.userEntered}
                            </CardTitle>
                          </CardHeader>
                          <CardContent className="flex flex-col items-center justify-center text-center flex-1 space-y-4">
                            <p className="text-sm text-gray-600 dark:text-gray-400">
                              {t.entities.userEnteredDescription}
                            </p>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-9 min-w-0 text-gray-900 hover:text-gray-700 dark:text-white dark:hover:text-gray-200"
                              onClick={() => setShowVirtualConfirm(true)}
                            >
                              <Download className="mr-2 h-4 w-4 flex-shrink-0" />
                              {t.entities.importData}
                            </Button>
                          </CardContent>
                        </Card>
                      )}

                      {/* Commodity Data Entry - only show when enabled */}
                      {isCommodityDataEntryAvailable() && (
                        <Card className="transition-all hover:shadow-md border-l-4 border-l-green-500 flex flex-col h-full">
                          <CardHeader className="pb-2">
                            <CardTitle className="flex items-center justify-center">
                              <CommodityIconsStack
                                positionsData={positionsData}
                              />
                              <span className="ml-2">
                                {t.entities.commodities}
                              </span>
                            </CardTitle>
                          </CardHeader>
                          <CardContent className="flex flex-col items-center justify-center text-center flex-1 space-y-4">
                            <p className="text-sm text-gray-600 dark:text-gray-400">
                              {t.entities.commoditiesDescription}
                            </p>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-9 min-w-0 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100"
                              onClick={() => setShowManageCommodities(true)}
                            >
                              <Settings className="mr-2 h-4 w-4 flex-shrink-0" />
                              {t.entities.manage}
                            </Button>
                          </CardContent>
                        </Card>
                      )}
                    </div>
                  </div>
                )}
              </motion.div>
            )}

            {(unconnectedEntities.length > 0 || !virtualEnabled) && (
              <motion.div variants={item} className="space-y-6">
                <h2 className="text-xl font-semibold">
                  {t.entities.available}
                </h2>

                {/* Financial Institutions */}
                {unconnectedFinancialEntities.length > 0 && (
                  <div className="space-y-3">
                    <h3 className="text-lg font-medium text-gray-700 dark:text-gray-300 flex items-center">
                      <Landmark className="h-5 w-5 mr-2" />
                      {t.entities.financialInstitutions}
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                      {unconnectedFinancialEntities.map(entity => (
                        <EntityCard
                          key={entity.id}
                          entity={entity}
                          onSelect={() => handleEntitySelect(entity)}
                          onRelogin={() => handleRelogin(entity)}
                          onDisconnect={() => handleDisconnect(entity)}
                          onManage={() => handleManage(entity)}
                        />
                      ))}
                    </div>
                  </div>
                )}

                {/* Crypto Wallets */}
                {unconnectedCryptoEntities.length > 0 && (
                  <div className="space-y-3">
                    <h3 className="text-lg font-medium text-gray-700 dark:text-gray-300 flex items-center">
                      <Wallet className="h-5 w-5 mr-2" />
                      {t.entities.cryptoWallets}
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                      {unconnectedCryptoEntities.map(entity => (
                        <EntityCard
                          key={entity.id}
                          entity={entity}
                          onSelect={() => handleEntitySelect(entity)}
                          onRelogin={() => handleRelogin(entity)}
                          onDisconnect={() => handleDisconnect(entity)}
                          onManage={() => handleManage(entity)}
                        />
                      ))}
                    </div>
                  </div>
                )}

                {/* User Entered (Virtual) and Commodities - Show in Available when disabled */}
                {(!virtualEnabled || !isCommodityDataEntryAvailable()) && (
                  <div className="space-y-3">
                    <h3 className="text-lg font-medium text-gray-700 dark:text-gray-300 flex items-center">
                      <User className="h-5 w-5 mr-2" />
                      {t.entities.manualDataEntry}
                    </h3>
                    {(!virtualEnabled || !isCommodityDataEntryAvailable()) && (
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {/* User Entered (Virtual) - Show when disabled */}
                        {!virtualEnabled && (
                          <Card className="transition-all hover:shadow-md border-l-4 border-l-gray-300 dark:border-l-gray-600 flex flex-col h-full">
                            <CardHeader className="pb-2">
                              <CardTitle className="flex items-center justify-center">
                                <FileSpreadsheet className="h-5 w-5 mr-2" />
                                {t.entities.userEntered}
                              </CardTitle>
                            </CardHeader>
                            <CardContent className="flex flex-col items-center justify-center text-center flex-1">
                              <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                                {t.entities.userEnteredAvailableDescription}
                              </p>
                              <Button
                                variant="outline"
                                className="w-full"
                                onClick={handleConfigureVirtual}
                              >
                                {t.entities.configureInSettings}
                              </Button>
                            </CardContent>
                          </Card>
                        )}

                        {/* Commodity Data Entry - show when disabled */}
                        {!isCommodityDataEntryAvailable() && (
                          <Card
                            className="transition-all hover:shadow-md border-l-4 border-l-gray-300 dark:border-l-gray-600 opacity-80 cursor-pointer hover:opacity-100 flex flex-col h-full"
                            onClick={() => {
                              setShowManageCommodities(true)
                            }}
                          >
                            <CardHeader className="pb-2">
                              <CardTitle className="flex items-center justify-center">
                                <CommodityIconsStack
                                  positionsData={positionsData}
                                />
                                <span className="ml-2">
                                  {t.entities.commodities}
                                </span>
                              </CardTitle>
                            </CardHeader>
                            <CardContent className="flex flex-col items-center justify-center text-center flex-1">
                              <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                                {t.entities.commoditiesDescription}
                              </p>
                            </CardContent>
                          </Card>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </motion.div>
            )}
          </motion.div>
        ) : null}

        {view === "login" && selectedEntity && !pinRequired && (
          <motion.div
            key="login"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
          >
            <Button variant="ghost" onClick={handleBack} className="mb-4">
              ← {t.common.back}
            </Button>
            {isLoading ? (
              <div className="flex flex-col justify-center items-center h-64">
                <LoadingSpinner size="lg" />
                <p className="mt-4 text-gray-500 dark:text-gray-400">
                  {t.common.loading}
                </p>
              </div>
            ) : (
              <LoginForm />
            )}
          </motion.div>
        )}

        {view === "external-login" && selectedEntity && (
          <motion.div
            key="external-login"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
          >
            <Button
              variant="ghost"
              onClick={handleBack}
              className="mb-4"
              disabled={externalLoginInProgress}
            >
              ← {t.common.back}
            </Button>
            <Card className="w-full max-w-md mx-auto">
              <CardHeader>
                <CardTitle className="text-center flex items-center justify-center">
                  <ExternalLink className="mr-2 h-5 w-5" />
                  {t.login.externalLogin} {selectedEntity.name}
                </CardTitle>
              </CardHeader>
              <CardContent className="text-center">
                {externalLoginInProgress ? (
                  <div className="flex flex-col items-center justify-center py-8">
                    <LoadingSpinner size="lg" className="mb-4" />
                    <p>{t.login.externalLoginInProgress}</p>
                  </div>
                ) : (
                  <div className="py-8">
                    <p className="mb-4">{t.login.externalLoginComplete}</p>
                    <Button onClick={handleBack}>{t.common.back}</Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        )}

        {view === "features" && selectedEntity && !pinRequired && (
          <motion.div
            key="features"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="min-h-[calc(100vh-18rem)] flex flex-col"
          >
            <Button
              variant="ghost"
              onClick={handleBack}
              className="mb-4 self-start"
            >
              ← {t.common.back}
            </Button>
            <div className="flex-1 flex justify-center items-center">
              <FeatureSelector />
            </div>
          </motion.div>
        )}

        {pinRequired && selectedEntity && (
          <motion.div
            key="pinpad"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="min-h-[calc(100vh-18rem)] flex flex-col"
          >
            <Button
              variant="ghost"
              onClick={handleBack}
              className="mb-4 self-start"
            >
              ← {t.common.back}
            </Button>
            {isLoading ? (
              <div className="flex flex-col justify-center items-center h-64">
                <LoadingSpinner size="lg" />
                <p className="mt-4 text-gray-500 dark:text-gray-400">
                  {t.common.loading}
                </p>
              </div>
            ) : (
              <div className="flex-1 flex justify-center items-center">
                <PinPad />
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Add Wallet Modal */}
      <AnimatePresence>
        {showAddWallet && selectedEntity && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="max-w-md w-full mx-4"
            >
              <AddWalletForm
                entity={selectedEntity}
                onSubmit={handleAddWallet}
                onCancel={handleCancelAddWallet}
                isLoading={isAddingWallet}
              />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Manage Wallets Modal */}
      <AnimatePresence>
        {showManageWallets && selectedEntity && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-white dark:bg-gray-900 rounded-lg shadow-2xl border border-gray-200 dark:border-gray-700 w-full max-w-6xl max-h-[90vh] overflow-hidden"
            >
              <div className="h-full overflow-y-auto p-6">
                <ManageWalletsView
                  entityId={selectedEntity.id}
                  onBack={handleBackFromManageWallets}
                  onAddWallet={handleAddWalletFromManage}
                  onWalletUpdated={fetchEntities}
                  onClose={handleBackFromManageWallets}
                />
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Manage Commodities Modal */}
      <AnimatePresence>
        {showManageCommodities && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-white dark:bg-gray-900 rounded-lg shadow-2xl border border-gray-200 dark:border-gray-700 w-full max-w-6xl max-h-[90vh] overflow-hidden"
            >
              <div className="h-full overflow-y-auto p-6">
                <ManageCommoditiesView
                  onBack={handleBackFromManageCommodities}
                />
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <ConfirmationDialog
        isOpen={showVirtualConfirm}
        title={t.entities.confirmUserEntered}
        message={t.entities.confirmUserEnteredDescription}
        confirmText={t.common.confirm}
        cancelText={t.common.cancel}
        onConfirm={handleVirtualConfirm}
        onCancel={handleVirtualCancel}
        isLoading={isVirtualScraping}
      />

      <ErrorDetailsDialog
        isOpen={showErrorDetails}
        errors={virtualErrors || []}
        onClose={handleCloseErrorDetails}
      />
    </div>
  )
}
