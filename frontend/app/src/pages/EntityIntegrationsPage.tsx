import { useAppContext } from "@/context/AppContext"
import { useEntityWorkflow } from "@/context/EntityWorkflowContext"
import { EntityCard } from "@/components/EntityCard"
import { LoginForm } from "@/components/LoginForm"
import { AddWalletForm } from "@/components/AddWalletForm"
import { ManageWalletsView } from "@/components/ManageWalletsView"
import { PinPad } from "@/components/PinPad"
import { FeatureSelector } from "@/components/FeatureSelector"
import { Button } from "@/components/ui/Button"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { useI18n } from "@/i18n"
import { motion, AnimatePresence } from "framer-motion"
import { fadeListContainer, fadeListItem } from "@/lib/animations"
import { useState, useEffect } from "react"
import { useLocation } from "react-router-dom"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { ExternalLink, Landmark, Wallet, Check } from "lucide-react"
import {
  EntityOrigin,
  EntitySetupLoginType,
  EntityStatus,
  EntityType,
  ExternalIntegrationType,
  ExternalIntegrationStatus,
  ExternalEntityConnectionResult,
  ExternalEntitySetupResponseCode,
  CryptoWalletConnectionResult,
} from "@/types"
import {
  createCryptoWallet,
  getExternalEntityCandidates,
  connectExternalEntity,
  completeExternalEntityConnection,
  getImageUrl,
  disconnectExternalEntity,
} from "@/services/api"
import { AVAILABLE_COUNTRIES, getCountryFlag } from "@/constants/countries"
import { isNativeMobile } from "@/lib/platform"

export default function EntityIntegrationsPage() {
  const {
    entities,
    isLoadingEntities,
    fetchEntities,
    showToast,
    externalIntegrations,
  } = useAppContext()
  const {
    isLoggingIn,
    selectedEntity,
    pinRequired,
    selectEntity,
    scrape,
    view,
    setView,
    startExternalLogin,
    disconnectEntity,
  } = useEntityWorkflow()

  const { t } = useI18n()
  const [showAddWallet, setShowAddWallet] = useState(false)
  const [isAddingWallet, setIsAddingWallet] = useState(false)
  const [showManageWallets, setShowManageWallets] = useState(false)
  // External entity linking state
  const [showAddExternalEntity, setShowAddExternalEntity] = useState(false)
  const [selectedCountry, setSelectedCountry] = useState<string | null>(null)
  const [candidatesLoading, setCandidatesLoading] = useState(false)
  const [candidatesError, setCandidatesError] = useState<string | null>(null)
  const [externalCandidates, setExternalCandidates] = useState<
    { id: string; name: string; bic: string; icon?: string | null }[]
  >([])
  const [connectingInstitutionId, setConnectingInstitutionId] = useState<
    string | null
  >(null)
  const [showCompleteExternalModal, setShowCompleteExternalModal] =
    useState(false)
  const [externalLink, setExternalLink] = useState<string | null>(null)
  // External entity id returned by connect endpoint (used to complete)
  const [externalEntityId, setExternalEntityId] = useState<string | null>(null)
  const [completingConnection, setCompletingConnection] = useState(false)
  const [alreadyLinked, setAlreadyLinked] = useState(false)
  const [candidateIcons, setCandidateIcons] = useState<Record<string, string>>(
    {},
  )
  // Linking existing externally provided entity
  const [linkingExternalEntityId, setLinkingExternalEntityId] = useState<
    string | null
  >(null)

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

  const connectedEntities =
    entities?.filter(
      entity => isEntityConnected(entity) && entity.origin !== "MANUAL",
    ) || []

  const unconnectedEntities =
    entities?.filter(
      entity =>
        isEntityDisconnected(entity) &&
        entity.origin !== "MANUAL" &&
        entity.origin !== EntityOrigin.EXTERNALLY_PROVIDED,
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

    if (entity.type === EntityType.CRYPTO_WALLET) {
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

  const handleAddWallet = async (
    name: string,
    addresses: string[],
  ): Promise<CryptoWalletConnectionResult | void> => {
    if (!selectedEntity) return

    const normalizedAddresses = addresses.map(address => address.trim())

    setIsAddingWallet(true)
    try {
      const result = await createCryptoWallet({
        entityId: selectedEntity.id,
        name,
        addresses: normalizedAddresses,
      })

      const failedEntries = result?.failed ?? {}
      const failedCount = Object.keys(failedEntries).length
      const successCount = normalizedAddresses.length - failedCount

      if (successCount > 0) {
        await scrape(selectedEntity, selectedEntity.features)

        const toastMessage =
          successCount === normalizedAddresses.length
            ? t.walletForm.toasts.allSuccess
            : successCount === 1
              ? t.walletForm.toasts.partialSuccessSingle
              : t.walletForm.toasts.partialSuccessMultiple.replace(
                  "{count}",
                  successCount.toString(),
                )

        showToast(toastMessage, "success")
      }

      if (failedCount === 0) {
        setShowAddWallet(false)
        setView("entities")
      } else if (successCount === 0) {
        showToast(t.walletForm.toasts.allFailed, "error")
      }

      return result
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

  const handleAddWalletFromManage = () => {
    setShowManageWallets(false)
    setShowAddWallet(true)
  }

  // External integrations helpers
  const hasProviderIntegration = externalIntegrations.some(
    integ =>
      integ.type === ExternalIntegrationType.ENTITY_PROVIDER &&
      integ.status === ExternalIntegrationStatus.ON,
  )

  const openAddExternalEntity = () => {
    setShowAddExternalEntity(true)
    // Reset state
    setSelectedCountry(null)
    setExternalCandidates([])
    setCandidatesError(null)
    setAlreadyLinked(false)
  }

  const closeAddExternalEntity = () => {
    setShowAddExternalEntity(false)
  }

  const fetchCandidates = async (country: string) => {
    setSelectedCountry(country)
    setCandidatesLoading(true)
    setCandidatesError(null)
    setExternalCandidates([])
    try {
      const res = await getExternalEntityCandidates(country)
      setExternalCandidates(res.entities || [])
    } catch (e: any) {
      setCandidatesError(e?.message || "error")
    } finally {
      setCandidatesLoading(false)
    }
  }

  const handleConnectExternalEntity = async (institutionId: string) => {
    setConnectingInstitutionId(institutionId)
    setAlreadyLinked(false)
    try {
      const result: ExternalEntityConnectionResult =
        await connectExternalEntity({ institution_id: institutionId })
      if (result.code === ExternalEntitySetupResponseCode.ALREADY_LINKED) {
        setAlreadyLinked(true)
        await fetchEntities()
      } else if (
        result.code === ExternalEntitySetupResponseCode.CONTINUE_WITH_LINK &&
        result.link &&
        result.id
      ) {
        setExternalEntityId(result.id)
        setExternalLink(result.link)
        setShowAddExternalEntity(false)
        setShowCompleteExternalModal(true)
        try {
          window.open(result.link, "_blank")
        } catch {
          // ignore window open errors
        }
      }
    } catch {
      // ignore errors
    } finally {
      setConnectingInstitutionId(null)
    }
  }

  // Continue link for externally provided entities that require login
  const handleContinueExternalEntityLink = async (entity: any) => {
    if (!entity.external_entity_id) return
    setLinkingExternalEntityId(entity.id)
    try {
      const result: ExternalEntityConnectionResult =
        await connectExternalEntity({
          external_entity_id: entity.external_entity_id,
        })
      if (result.code === ExternalEntitySetupResponseCode.ALREADY_LINKED) {
        await fetchEntities()
      } else if (
        result.code === ExternalEntitySetupResponseCode.CONTINUE_WITH_LINK &&
        result.link &&
        result.id
      ) {
        setExternalEntityId(result.id)
        setExternalLink(result.link)
        setShowCompleteExternalModal(true)
        try {
          window.open(result.link, "_blank")
        } catch {
          /* empty */
        }
      }
    } catch {
      // ignore
    } finally {
      setLinkingExternalEntityId(null)
    }
  }

  const handleDisconnectExternalProvided = async (entity: any) => {
    if (!entity.external_entity_id) return
    try {
      await disconnectExternalEntity(entity.external_entity_id)
      await fetchEntities()
    } catch {
      // ignore
    }
  }

  const handleRelinkExternalProvided = async (entity: any) => {
    if (!entity.external_entity_id) return
    setLinkingExternalEntityId(entity.id)
    try {
      const result: ExternalEntityConnectionResult =
        await connectExternalEntity({
          external_entity_id: entity.external_entity_id,
          relink: true,
        })
      if (result.code === ExternalEntitySetupResponseCode.ALREADY_LINKED) {
        await fetchEntities()
      } else if (
        result.code === ExternalEntitySetupResponseCode.CONTINUE_WITH_LINK &&
        result.link &&
        result.id
      ) {
        setExternalEntityId(result.id)
        setExternalLink(result.link)
        setShowCompleteExternalModal(true)
        try {
          window.open(result.link, "_blank")
        } catch {
          /* empty */
        }
      }
    } catch {
      // ignore
    } finally {
      setLinkingExternalEntityId(null)
    }
  }

  const handleCompleteExternalConnection = async () => {
    if (!externalEntityId) return
    setCompletingConnection(true)
    try {
      await completeExternalEntityConnection(externalEntityId)
      await fetchEntities()
      setView("entities")
      setShowCompleteExternalModal(false)
    } catch {
      // ignore
    } finally {
      setCompletingConnection(false)
    }
  }

  // Load candidate icons when list changes
  useEffect(() => {
    let cancelled = false
    const load = async () => {
      const entries: [string, string][] = []
      for (const c of externalCandidates) {
        if (!c.icon) continue
        try {
          const src = c.icon
            ? c.icon.startsWith("/")
              ? await getImageUrl(c.icon)
              : c.icon
            : ""
          if (!cancelled && src) entries.push([c.id, src])
        } catch {
          // ignore
        }
      }
      if (!cancelled && entries.length > 0) {
        setCandidateIcons(prev => ({ ...prev, ...Object.fromEntries(entries) }))
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [externalCandidates])

  // Scroll to enabled crypto wallets section when URL hash is present
  const { hash } = useLocation()
  useEffect(() => {
    if (hash === "#crypto-enabled") {
      setTimeout(() => {
        const el = document.getElementById("crypto-enabled")
        if (el) {
          el.scrollIntoView({ behavior: "smooth", block: "start" })
        }
      }, 80)
    }
  }, [hash, connectedCryptoEntities.length, view])

  return (
    <motion.div
      className="space-y-6"
      variants={fadeListContainer}
      initial="hidden"
      animate="show"
    >
      <motion.div
        className="flex justify-between items-center"
        variants={fadeListItem}
      >
        <h1 className="text-3xl font-bold">{t.entities.title}</h1>
      </motion.div>

      <motion.div variants={fadeListItem}>
        <AnimatePresence mode="wait">
          {isLoadingEntities ? (
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
          ) : (
            <motion.div
              key="entities"
              variants={fadeListContainer}
              initial="hidden"
              animate="show"
              className="space-y-8"
            >
              {connectedEntities.length > 0 && (
                <motion.div variants={fadeListItem} className="space-y-6">
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
                      <motion.div
                        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
                        variants={fadeListContainer}
                        initial={false}
                        animate="show"
                      >
                        {connectedFinancialEntities.map(entity => (
                          <motion.div key={entity.id} variants={fadeListItem}>
                            <EntityCard
                              entity={entity}
                              onSelect={() => handleEntitySelect(entity)}
                              onRelogin={() => handleRelogin(entity)}
                              onDisconnect={() => handleDisconnect(entity)}
                              onManage={() => handleManage(entity)}
                              onExternalContinue={
                                handleContinueExternalEntityLink
                              }
                              onExternalDisconnect={
                                handleDisconnectExternalProvided
                              }
                              linkingExternalEntityId={linkingExternalEntityId}
                              onExternalRelink={handleRelinkExternalProvided}
                            />
                          </motion.div>
                        ))}
                      </motion.div>
                    </div>
                  )}

                  {/* Crypto Wallets */}
                  {connectedCryptoEntities.length > 0 && (
                    <div className="space-y-3" id="crypto-enabled">
                      <h3 className="text-lg font-medium text-gray-700 dark:text-gray-300 flex items-center">
                        <Wallet className="h-5 w-5 mr-2" />
                        {t.entities.cryptoWallets}
                      </h3>
                      <motion.div
                        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
                        variants={fadeListContainer}
                        initial={false}
                        animate="show"
                      >
                        {connectedCryptoEntities.map(entity => (
                          <motion.div key={entity.id} variants={fadeListItem}>
                            <EntityCard
                              entity={entity}
                              onSelect={() => handleEntitySelect(entity)}
                              onRelogin={() => handleRelogin(entity)}
                              onDisconnect={() => handleDisconnect(entity)}
                              onManage={() => handleManage(entity)}
                              onExternalContinue={
                                handleContinueExternalEntityLink
                              }
                              onExternalDisconnect={
                                handleDisconnectExternalProvided
                              }
                              linkingExternalEntityId={linkingExternalEntityId}
                            />
                          </motion.div>
                        ))}
                      </motion.div>
                    </div>
                  )}
                </motion.div>
              )}

              <motion.div variants={fadeListItem} className="space-y-6">
                <h2 className="text-xl font-semibold">
                  {t.entities.available}
                </h2>

                {/* Financial Institutions */}
                <div className="space-y-3">
                  <h3 className="text-lg font-medium text-gray-700 dark:text-gray-300 flex items-center">
                    <Landmark className="h-5 w-5 mr-2" />
                    {t.entities.financialInstitutions}
                  </h3>
                  <motion.div
                    className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
                    variants={fadeListContainer}
                  >
                    {/* Add External Entity Card */}
                    {hasProviderIntegration && (
                      <motion.div variants={fadeListItem}>
                        <Card
                          className={`transition-all border-l-4 border-l-gray-300 ${
                            isNativeMobile()
                              ? "opacity-60 cursor-not-allowed"
                              : "opacity-100 cursor-pointer hover:shadow-lg hover:shadow-md"
                          }`}
                          onClick={() => {
                            if (!isNativeMobile()) {
                              openAddExternalEntity()
                            }
                          }}
                        >
                          <CardHeader className="pb-0 p-4">
                            <CardTitle className="flex items-center justify-between gap-2 flex-wrap">
                              <div className="flex items-center min-w-0">
                                <div className="w-12 h-12 mr-3 flex-shrink-0 relative">
                                  <div className="absolute inset-0">
                                    <img
                                      src="icons/santander.png"
                                      alt=""
                                      className="absolute top-0 left-1/2 -translate-x-1/2 w-6 h-6 object-contain rounded"
                                      style={{
                                        transform:
                                          "translate(-50%,-10%) rotate(-10deg)",
                                      }}
                                      draggable={false}
                                    />
                                    <img
                                      src="icons/sabadell.png"
                                      alt=""
                                      className="absolute left-0 top-1/2 -translate-y-1/2 w-6 h-6 object-contain rounded"
                                      style={{
                                        transform:
                                          "translate(0,-45%) rotate(6deg)",
                                      }}
                                      draggable={false}
                                    />
                                    <img
                                      src="icons/n26.png"
                                      alt=""
                                      className="absolute bottom-0 left-1/2 -translate-x-1/2 w-6 h-6 object-contain rounded"
                                      style={{
                                        transform:
                                          "translate(-55%,10%) rotate(9deg)",
                                      }}
                                      draggable={false}
                                    />
                                    <img
                                      src="icons/vivid.png"
                                      alt=""
                                      className="absolute right-0 top-1/2 -translate-y-1/2 w-6 h-6 object-contain rounded"
                                      style={{
                                        transform:
                                          "translate(0%,-45%) rotate(-7deg)",
                                      }}
                                      draggable={false}
                                    />
                                  </div>
                                </div>
                                <span className="truncate">
                                  {t.entities.moreFinancialInstitutionsCard}
                                </span>
                              </div>
                              {isNativeMobile() && (
                                <span className="text-xs text-muted-foreground">
                                  {t.common.notAvailableOnPlatform}
                                </span>
                              )}
                            </CardTitle>
                          </CardHeader>
                        </Card>
                      </motion.div>
                    )}
                    {unconnectedFinancialEntities.map(entity => (
                      <motion.div key={entity.id} variants={fadeListItem}>
                        <EntityCard
                          entity={entity}
                          onSelect={() => handleEntitySelect(entity)}
                          onRelogin={() => handleRelogin(entity)}
                          onDisconnect={() => handleDisconnect(entity)}
                          onManage={() => handleManage(entity)}
                          onExternalContinue={handleContinueExternalEntityLink}
                          onExternalDisconnect={
                            handleDisconnectExternalProvided
                          }
                          linkingExternalEntityId={linkingExternalEntityId}
                          onExternalRelink={handleRelinkExternalProvided}
                        />
                      </motion.div>
                    ))}
                  </motion.div>
                </div>

                {/* Crypto Wallets */}
                {unconnectedCryptoEntities.length > 0 && (
                  <div className="space-y-3">
                    <h3 className="text-lg font-medium text-gray-700 dark:text-gray-300 flex items-center">
                      <Wallet className="h-5 w-5 mr-2" />
                      {t.entities.cryptoWallets}
                    </h3>
                    <motion.div
                      className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
                      variants={fadeListContainer}
                    >
                      {unconnectedCryptoEntities.map(entity => (
                        <motion.div key={entity.id} variants={fadeListItem}>
                          <EntityCard
                            entity={entity}
                            onSelect={() => handleEntitySelect(entity)}
                            onRelogin={() => handleRelogin(entity)}
                            onDisconnect={() => handleDisconnect(entity)}
                            onManage={() => handleManage(entity)}
                            onExternalContinue={
                              handleContinueExternalEntityLink
                            }
                            onExternalDisconnect={
                              handleDisconnectExternalProvided
                            }
                            linkingExternalEntityId={linkingExternalEntityId}
                            onExternalRelink={handleRelinkExternalProvided}
                          />
                        </motion.div>
                      ))}
                    </motion.div>
                  </div>
                )}
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {/* Login Modal */}
      <AnimatePresence>
        {view === "login" && selectedEntity && !pinRequired && (
          <motion.div
            key="login-modal"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 px-4 py-8"
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="relative w-full max-w-md mx-auto"
            >
              {isLoggingIn ? (
                <div className="flex flex-col justify-center items-center h-64 rounded-lg border border-border bg-background px-6">
                  <LoadingSpinner size="lg" />
                  <p className="mt-4 text-gray-500 dark:text-gray-400">
                    {t.common.loading}
                  </p>
                </div>
              ) : (
                <LoginForm />
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* External Login Modal */}
      <AnimatePresence>
        {view === "external-login" && selectedEntity && (
          <motion.div
            key="external-login-modal"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 px-4 py-8"
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="relative w-full max-w-md mx-auto"
            >
              <Card className="w-full">
                <CardHeader>
                  <CardTitle className="text-center flex items-center justify-center">
                    <ExternalLink className="mr-2 h-5 w-5" />
                    {t.login.externalLogin} {selectedEntity.name}
                  </CardTitle>
                </CardHeader>
                <CardContent className="text-center">
                  <div className="flex flex-col items-center justify-center py-8">
                    <LoadingSpinner size="lg" className="mb-4" />
                    <p>{t.login.externalLoginInProgress}</p>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Feature Selector Modal */}
      <AnimatePresence>
        {view === "features" && selectedEntity && !pinRequired && (
          <motion.div
            key="features-modal"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 px-4 py-8"
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="relative w-full max-w-md mx-auto"
            >
              <FeatureSelector />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* PIN Modal */}
      <AnimatePresence>
        {pinRequired && selectedEntity && (
          <motion.div
            key="pin-modal"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 px-4 py-8"
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="relative w-full max-w-md mx-auto"
            >
              {isLoggingIn ? (
                <div className="flex flex-col justify-center items-center h-64 rounded-lg border border-border bg-background px-6">
                  <LoadingSpinner size="lg" />
                  <p className="mt-4 text-gray-500 dark:text-gray-400">
                    {t.common.loading}
                  </p>
                </div>
              ) : (
                <PinPad />
              )}
            </motion.div>
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
            className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-40"
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
            className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-40 p-4"
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-white dark:bg-gray-900 rounded-lg shadow-2xl border border-gray-200 dark:border-gray-700 w-full max-w-6xl max-h-[90vh] flex flex-col overflow-hidden"
            >
              <div className="flex-1 overflow-y-auto p-6 min-h-0">
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

      {/* Add External Entity Modal */}
      <AnimatePresence>
        {showAddExternalEntity && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-40 p-4"
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-white dark:bg-gray-900 rounded-lg shadow-2xl border border-gray-200 dark:border-gray-700 w-full max-w-4xl max-h-[85vh] flex flex-col"
            >
              <div className="flex flex-col h-full min-h-0">
                <div className="px-6 pt-6 pb-4 border-b border-gray-200 dark:border-gray-700">
                  <h3 className="text-lg font-semibold">
                    {t.entities.addExternalEntity}
                  </h3>
                </div>
                <div className="flex-1 overflow-y-auto p-6 space-y-8 min-h-0">
                  <div>
                    <h4 className="text-sm font-medium mb-2">
                      {t.entities.selectCountry}
                    </h4>
                    <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 lg:grid-cols-10 gap-2">
                      {AVAILABLE_COUNTRIES.filter(code => code !== "XX").map(
                        code => (
                          <button
                            key={code}
                            onClick={() => fetchCandidates(code)}
                            className={`border rounded-md py-2 text-sm flex flex-col items-center justify-center gap-1 transition-colors ${selectedCountry === code ? "bg-gray-200 dark:bg-gray-700 border-gray-400 dark:border-gray-500" : "hover:bg-gray-100 dark:hover:bg-gray-800 border-gray-200 dark:border-gray-700"}`}
                          >
                            <span className="text-xl leading-none">
                              {getCountryFlag(code)}
                            </span>
                            <span className="text-[10px] font-medium">
                              {code}
                            </span>
                          </button>
                        ),
                      )}
                    </div>
                  </div>
                  {selectedCountry && (
                    <div>
                      <h4 className="text-sm font-medium mb-2">
                        {t.entities.selectInstitution}
                      </h4>
                      {candidatesLoading && (
                        <div className="py-8 flex justify-center">
                          <LoadingSpinner size="lg" />
                        </div>
                      )}
                      {candidatesError && (
                        <div className="text-sm text-red-600 dark:text-red-400">
                          {candidatesError}
                        </div>
                      )}
                      {!candidatesLoading && !candidatesError && (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                          {externalCandidates.length === 0 && (
                            <div className="text-sm text-gray-500 dark:text-gray-400 col-span-full">
                              {t.entities.noInstitutionsFound}
                            </div>
                          )}
                          {externalCandidates.map(c => {
                            const isConnecting =
                              connectingInstitutionId === c.id
                            const iconSrc = candidateIcons[c.id]
                            return (
                              <Card
                                key={c.id}
                                className={`p-4 cursor-pointer flex items-center gap-4 h-20 border border-gray-200 dark:border-gray-700 hover:border-primary/60 dark:hover:border-primary/60 transition-colors group`}
                                onClick={() => {
                                  if (
                                    connectingInstitutionId &&
                                    connectingInstitutionId !== c.id
                                  )
                                    return
                                  handleConnectExternalEntity(c.id)
                                }}
                              >
                                {isConnecting ? (
                                  <div className="w-full flex flex-col items-center justify-center gap-2">
                                    <LoadingSpinner size="sm" />
                                    <span className="text-xs text-gray-600 dark:text-gray-300">
                                      {t.entities.connecting}
                                    </span>
                                  </div>
                                ) : (
                                  <>
                                    <div className="w-10 h-10 rounded-md flex items-center justify-center overflow-hidden flex-shrink-0">
                                      {iconSrc ? (
                                        <img
                                          src={iconSrc}
                                          alt={c.name}
                                          className="w-10 h-10 object-contain"
                                        />
                                      ) : (
                                        <Landmark className="h-5 w-5 text-gray-500" />
                                      )}
                                    </div>
                                    <div className="min-w-0 flex-1">
                                      <div className="font-medium truncate group-hover:text-primary">
                                        {c.name}
                                      </div>
                                      <div className="text-xs text-gray-500 dark:text-gray-400 mt-1 truncate">
                                        {c.bic}
                                      </div>
                                    </div>
                                  </>
                                )}
                              </Card>
                            )
                          })}
                        </div>
                      )}
                      {alreadyLinked && (
                        <div className="mt-4 text-sm flex items-center gap-2 text-green-600 dark:text-green-400">
                          <Check className="h-4 w-4" />
                          {t.entities.alreadyLinked}
                        </div>
                      )}
                    </div>
                  )}
                </div>
                <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700 flex justify-end">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={closeAddExternalEntity}
                  >
                    {t.common.close}
                  </Button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Complete External Entity Connection Modal */}
      <AnimatePresence>
        {showCompleteExternalModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-40 p-4"
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-white dark:bg-gray-900 rounded-lg shadow-2xl border border-gray-200 dark:border-gray-700 w-full max-w-md overflow-hidden"
            >
              <div className="p-6 space-y-4">
                <h3 className="text-lg font-semibold">
                  {t.entities.confirmConnection}
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  {t.entities.providerLinkInstructions}
                </p>
                <div className="flex flex-col gap-2">
                  {externalLink && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        try {
                          window.open(externalLink, "_blank")
                        } catch {
                          // ignore
                        }
                      }}
                    >
                      {t.entities.openLink}
                    </Button>
                  )}
                  <Button
                    size="sm"
                    onClick={handleCompleteExternalConnection}
                    disabled={completingConnection}
                  >
                    {completingConnection
                      ? t.common.loading
                      : t.entities.confirmConnection}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={async () => {
                      setShowCompleteExternalModal(false)
                      try {
                        await fetchEntities()
                      } catch {
                        /* ignore */
                      }
                      setView("entities")
                    }}
                  >
                    {t.entities.dismiss}
                  </Button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
