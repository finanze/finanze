import { useEffect, useState } from "react"

import type { Entity } from "@/types"
import {
  EntityStatus,
  EntityType,
  ExternalIntegrationStatus,
  EntityOrigin,
} from "@/types"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { Badge } from "@/components/ui/Badge"
import { Button } from "@/components/ui/Button"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { FeaturesBadge } from "@/components/ui/FeaturesBadge"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import { useAppContext } from "@/context/AppContext"
import { useEntityWorkflow } from "@/context/EntityWorkflowContext"
import { useI18n } from "@/i18n"
import {
  RefreshCw,
  Trash2,
  Settings,
  Wallet,
  Download,
  LogIn,
  AlertCircle,
} from "lucide-react"
import { ConfirmationDialog } from "@/components/ui/ConfirmationDialog"
import { useNavigate } from "react-router-dom"
import { getImageUrl } from "@/services/api"

interface EntityCardProps {
  entity: Entity
  onSelect: () => void
  onRelogin: () => void
  onDisconnect: () => void
  onManage?: () => void
  onExternalContinue?: (entity: Entity) => void
  onExternalDisconnect?: (entity: Entity) => Promise<void> | void
  linkingExternalEntityId?: string | null
  onExternalRelink?: (entity: Entity) => Promise<void> | void
}

export function EntityCard({
  entity,
  onSelect,
  onRelogin,
  onDisconnect,
  onManage,
  onExternalContinue,
  onExternalDisconnect,
  linkingExternalEntityId,
  onExternalRelink,
}: EntityCardProps) {
  const { t } = useI18n()
  const { externalIntegrations } = useAppContext()
  const { fetchingEntityState } = useEntityWorkflow()
  const navigate = useNavigate()
  const [showConfirmation, setShowConfirmation] = useState(false)
  const [showExternalConfirmation, setShowExternalConfirmation] =
    useState(false)
  const [showRelinkConfirmation, setShowRelinkConfirmation] = useState(false)
  const [relinkingLoading, setRelinkingLoading] = useState(false)
  const [externalDisconnectLoading, setExternalDisconnectLoading] =
    useState(false)

  const { fetchingEntityIds } = fetchingEntityState

  // Check if this entity is currently being fetched
  const entityFetching = fetchingEntityIds.includes(entity.id)

  // Helper function to check if required external integrations are enabled
  const areRequiredIntegrationsEnabled = () => {
    if (
      !entity.required_external_integrations ||
      entity.required_external_integrations.length === 0
    ) {
      return true
    }

    return entity.required_external_integrations.every(requiredId => {
      const integration = externalIntegrations.find(
        integration => integration.id === requiredId,
      )
      return integration?.status === ExternalIntegrationStatus.ON
    })
  }

  // Helper function to get missing integration names
  const getMissingIntegrationNames = () => {
    if (!entity.required_external_integrations) return []

    return entity.required_external_integrations
      .map(requiredId => {
        const integration = externalIntegrations.find(
          integration => integration.id === requiredId,
        )
        if (
          !integration ||
          integration.status !== ExternalIntegrationStatus.ON
        ) {
          return integration?.name || requiredId
        }
        return null
      })
      .filter(name => name !== null)
  }

  // Helper function to determine if a crypto wallet entity is connected
  const isCryptoWalletConnected = () => {
    return (
      entity.type === EntityType.CRYPTO_WALLET &&
      entity.connected &&
      entity.connected.length > 0
    )
  }

  // Helper function to get effective status for entities
  const getEffectiveStatus = () => {
    if (entity.type === EntityType.CRYPTO_WALLET) {
      return isCryptoWalletConnected()
        ? EntityStatus.CONNECTED
        : EntityStatus.DISCONNECTED
    }
    return entity.status
  }

  const effectiveStatus = getEffectiveStatus()
  const missingIntegrations = !areRequiredIntegrationsEnabled()

  // Helper function to determine if entity is in danger state (connected but missing integrations)
  const isDangerState = () => {
    return effectiveStatus === EntityStatus.CONNECTED && missingIntegrations
  }

  // Determine card styling based on effective entity status
  const getCardStyle = () => {
    // If connected but missing integrations, show red (danger state)
    if (isDangerState()) {
      return "border-l-4 border-l-red-500"
    }

    switch (effectiveStatus) {
      case EntityStatus.CONNECTED:
        return "border-l-4 border-l-green-500"
      case EntityStatus.REQUIRES_LOGIN:
        return "border-l-4 border-l-amber-500"
      default:
        return "border-l-4 border-l-gray-300 opacity-80"
    }
  }

  // Determine badge styling and text based on effective entity status
  const getBadgeInfo = () => {
    // Always check if integrations are missing first (regardless of connection status)
    if (missingIntegrations) {
      const missingNames = getMissingIntegrationNames()
      const requiresText =
        missingNames.length === 1
          ? `${t.entities.requires} ${missingNames[0]}`
          : `${t.entities.requires} ${missingNames.length} ${t.entities.integrations}`

      return {
        style: isDangerState()
          ? "bg-red-100 text-red-700 hover:bg-red-200 dark:bg-red-900/20 dark:text-red-300 dark:hover:bg-red-900/30 cursor-pointer transition-colors"
          : "hover:bg-red-100 hover:text-red-700 dark:hover:bg-red-900/20 dark:hover:text-red-300 cursor-pointer transition-colors",
        text: requiresText,
        isMissingIntegrations: true,
        missingNames,
      }
    }

    switch (effectiveStatus) {
      case EntityStatus.CONNECTED:
        return {
          style:
            "bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-300",
          text: t.entities.connected,
          isMissingIntegrations: false,
        }
      case EntityStatus.REQUIRES_LOGIN:
        return {
          style:
            "bg-amber-100 text-amber-800 dark:bg-amber-900/20 dark:text-amber-300",
          text: t.entities.requiresLogin,
          isMissingIntegrations: false,
        }
      default:
        return null
    }
  }

  // Determine button text based on entity type and status
  const getButtonText = () => {
    // If integrations are missing, show different text
    if (missingIntegrations) {
      return t.entities.cannotConnect
    }

    if (entity.type === EntityType.CRYPTO_WALLET) {
      return effectiveStatus === EntityStatus.CONNECTED
        ? t.entities.fetchData
        : t.entities.connect
    }

    switch (entity.status) {
      case EntityStatus.CONNECTED:
        return t.entities.fetchData
      case EntityStatus.REQUIRES_LOGIN:
        return t.entities.login
      default:
        return t.entities.connect
    }
  }

  // Handle disconnect button click
  const handleDisconnect = () => {
    setShowConfirmation(true)
  }

  const confirmDisconnect = () => {
    onDisconnect()
    setShowConfirmation(false)
  }

  const confirmExternalDisconnect = async () => {
    if (!onExternalDisconnect) return
    setExternalDisconnectLoading(true)
    try {
      await onExternalDisconnect(entity)
    } catch {
      // ignore
    } finally {
      setExternalDisconnectLoading(false)
      setShowExternalConfirmation(false)
    }
  }

  const confirmExternalRelink = async () => {
    if (!onExternalRelink) return
    setRelinkingLoading(true)
    try {
      await onExternalRelink(entity)
    } catch {
      // ignore
    } finally {
      setRelinkingLoading(false)
      setShowRelinkConfirmation(false)
    }
  }

  const cancelDisconnect = () => {
    setShowConfirmation(false)
  }

  const badgeInfo = getBadgeInfo()

  const isFinancialInstitution =
    entity.type === EntityType.FINANCIAL_INSTITUTION
  const isCryptoWallet = entity.type === EntityType.CRYPTO_WALLET

  const isDisconnected = effectiveStatus === EntityStatus.DISCONNECTED
  const canConnect =
    isDisconnected &&
    !missingIntegrations &&
    entity.origin !== EntityOrigin.EXTERNALLY_PROVIDED
  const isExternallyProvided =
    entity.origin === EntityOrigin.EXTERNALLY_PROVIDED
  const isLinkingExternal = linkingExternalEntityId === entity.id

  // Image source handling (external vs internal)
  const [imageSrc, setImageSrc] = useState<string>(`entities/${entity.id}.png`)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      if (entity.origin === EntityOrigin.EXTERNALLY_PROVIDED) {
        try {
          const src = await getImageUrl(
            `/static/entities/logos/${entity.id}.png`,
          )
          if (!cancelled) setImageSrc(src)
        } catch {
          if (!cancelled) setImageSrc(`entities/${entity.id}.png`)
        }
      } else {
        setImageSrc(`entities/${entity.id}.png`)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [entity.id, entity.origin])

  return (
    <>
      <Card
        className={`transition-all hover:shadow-md ${getCardStyle()} ${
          canConnect ? "cursor-pointer hover:opacity-100" : ""
        }`}
        onClick={canConnect ? onSelect : undefined}
      >
        <CardHeader className={isDisconnected ? "pb-0" : "pb-2"}>
          <CardTitle className="flex items-center justify-between gap-2 flex-wrap">
            <div className="flex items-center min-w-0 max-sm:w-full max-sm:justify-center">
              <div
                className={`${isDisconnected ? "w-8 h-8 mr-2" : "w-10 h-10 mr-3"} flex-shrink-0 overflow-hidden rounded-md`}
              >
                <img
                  src={imageSrc}
                  alt={entity.name}
                  className="w-full h-full object-contain"
                  onError={e =>
                    (e.currentTarget.src = "entities/entity_placeholder.png")
                  }
                />
              </div>
              <span className="truncate max-sm:text-center">{entity.name}</span>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0 max-sm:w-full max-sm:justify-center max-sm:flex-wrap">
              <FeaturesBadge features={entity.features} />
              {badgeInfo &&
                (badgeInfo.isMissingIntegrations ? (
                  <Popover>
                    <PopoverTrigger asChild>
                      <Badge
                        variant="outline"
                        className={`${badgeInfo.style} ${isDisconnected ? "text-xs py-0" : ""}`}
                      >
                        {badgeInfo.text}
                      </Badge>
                    </PopoverTrigger>
                    <PopoverContent className="w-80">
                      <div className="space-y-2">
                        <div className="flex items-center gap-2">
                          <AlertCircle className="h-9 w-9 text-red-500" />
                          <h4 className="font-medium text-sm">
                            {t.entities.setupIntegrationsMessage}
                          </h4>
                        </div>
                        <div className="space-y-1">
                          {(badgeInfo.missingNames || []).map((name, index) => (
                            <div key={index} className="text-sm ml-8">
                              • {name}
                            </div>
                          ))}
                        </div>
                        <Button
                          size="sm"
                          className="w-full mt-8"
                          onClick={() => navigate("/settings?tab=integrations")}
                        >
                          <Settings className="mr-2 h-3 w-3" />
                          {t.entities.goToSettings}
                        </Button>
                      </div>
                    </PopoverContent>
                  </Popover>
                ) : (
                  <Badge
                    variant="outline"
                    className={`${badgeInfo.style} ${isDisconnected ? "text-xs py-0" : ""}`}
                  >
                    {badgeInfo.text}
                  </Badge>
                ))}
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent className={isDisconnected ? "pt-0" : ""}>
          {/* Show connected wallets info for crypto entities */}
          {isCryptoWallet && effectiveStatus === EntityStatus.CONNECTED && (
            <div className="mt-3 p-2 bg-gray-50/50 dark:bg-gray-800/30 rounded-md border border-gray-200/50 dark:border-gray-700/50">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm">
                  <Wallet className="h-3 w-3 text-gray-500 dark:text-gray-400" />
                  <span className="text-gray-600 dark:text-gray-300 font-medium">
                    {entity.connected?.length === 1
                      ? `${entity.connected.length} wallet`
                      : `${entity.connected?.length} wallets`}
                  </span>
                </div>
                {entity.connected && entity.connected.length > 0 && (
                  <div className="flex gap-1 flex-wrap">
                    {entity.connected.slice(0, 3).map((wallet, index) => (
                      <Badge
                        key={index}
                        variant="secondary"
                        className="text-xs px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300"
                      >
                        {`•••${wallet.address.slice(-6)}`}
                      </Badge>
                    ))}
                    {entity.connected.length > 3 && (
                      <Badge
                        variant="secondary"
                        className="text-xs px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300"
                      >
                        +{entity.connected.length - 3}
                      </Badge>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Requires login - internal entities */}
          {effectiveStatus === EntityStatus.REQUIRES_LOGIN &&
            !isExternallyProvided && (
              <Button
                variant="ghost"
                size="sm"
                className="w-full mt-4 h-9 text-gray-900 font-bold hover:text-gray-700 dark:text-white dark:hover:text-gray-200"
                disabled={entityFetching}
                onClick={onSelect}
              >
                {entityFetching ? (
                  <>
                    <LoadingSpinner size="sm" />
                    <span className="ml-2">{t.common.loading}</span>
                  </>
                ) : (
                  <>
                    <LogIn className="mr-2 h-4 w-4" />
                    {getButtonText()}
                  </>
                )}
              </Button>
            )}

          {/* Requires login - externally provided entities (inline actions) */}
          {effectiveStatus === EntityStatus.REQUIRES_LOGIN &&
            isExternallyProvided && (
              <div className="flex gap-2 flex-wrap justify-center w-full mt-4">
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-gray-900 font-bold hover:text-gray-700 dark:text-white dark:hover:text-gray-200"
                  disabled={isLinkingExternal}
                  onClick={() =>
                    onExternalContinue && onExternalContinue(entity)
                  }
                >
                  {isLinkingExternal ? (
                    <>
                      <LoadingSpinner size="sm" />
                      <span className="ml-2">{t.common.loading}</span>
                    </>
                  ) : (
                    <>
                      <LogIn className="mr-2 h-4 w-4" />
                      {t.entities.continueLink}
                    </>
                  )}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300"
                  disabled={isLinkingExternal}
                  onClick={() => setShowExternalConfirmation(true)}
                >
                  <Trash2 className="mr-2 h-4 w-4 flex-shrink-0" />
                  {t.entities.disconnect}
                </Button>
              </div>
            )}

          {/* Show loading fetch button for connected entities when fetching */}
          {effectiveStatus === EntityStatus.CONNECTED &&
            !missingIntegrations &&
            entityFetching && (
              <Button
                variant="ghost"
                size="sm"
                className="w-full mt-4 h-9 text-gray-900 font-bold hover:text-gray-700 dark:text-white dark:hover:text-gray-200"
                disabled={true}
              >
                <LoadingSpinner size="sm" />
                <span className="ml-2">{t.common.fetching}</span>
              </Button>
            )}

          {/* Connected - externally provided entities */}
          {effectiveStatus === EntityStatus.CONNECTED &&
            !entityFetching &&
            isExternallyProvided && (
              <div className="flex gap-2 flex-wrap justify-center w-full mt-4">
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100"
                  onClick={() => setShowRelinkConfirmation(true)}
                  disabled={entityFetching}
                >
                  <RefreshCw className="mr-1 h-4 w-4 flex-shrink-0" />
                  {t.entities.relink}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-gray-900 font-bold hover:text-gray-700 dark:text-white dark:hover:text-gray-200"
                  disabled={entityFetching}
                  onClick={onSelect}
                >
                  {entityFetching ? (
                    <>
                      <LoadingSpinner size="sm" />
                      <span className="ml-2 flex-shrink-0">
                        {t.common.fetching}
                      </span>
                    </>
                  ) : (
                    <>
                      <Download className="mr-2 h-4 w-4 flex-shrink-0" />
                      {t.entities.fetchData}
                    </>
                  )}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300"
                  onClick={() => setShowExternalConfirmation(true)}
                  disabled={entityFetching}
                >
                  <Trash2 className="mr-1 h-4 w-4 flex-shrink-0" />
                  {t.entities.disconnect}
                </Button>
              </div>
            )}

          {/* Connected - internal entities */}
          {effectiveStatus === EntityStatus.CONNECTED &&
            !entityFetching &&
            !isExternallyProvided && (
              <div className="flex flex-col gap-2 mt-4 items-center w-full">
                {/* Financial institution buttons */}
                {isFinancialInstitution && (
                  <div className="flex gap-2 flex-wrap justify-center w-full">
                    {!missingIntegrations && (
                      <>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100"
                          onClick={onRelogin}
                          disabled={entityFetching}
                        >
                          <RefreshCw className="mr-1 h-4 w-4 flex-shrink-0" />
                          {t.entities.relogin}
                        </Button>

                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-gray-900 font-bold hover:text-gray-700 dark:text-white dark:hover:text-gray-200"
                          disabled={entityFetching}
                          onClick={onSelect}
                        >
                          {entityFetching ? (
                            <>
                              <LoadingSpinner size="sm" />
                              <span className="ml-2 flex-shrink-0">
                                {t.common.fetching}
                              </span>
                            </>
                          ) : (
                            <>
                              <Download className="mr-2 h-4 w-4 flex-shrink-0" />
                              {getButtonText()}
                            </>
                          )}
                        </Button>
                      </>
                    )}

                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300"
                      onClick={handleDisconnect}
                      disabled={entityFetching}
                    >
                      <Trash2 className="mr-1 h-4 w-4 flex-shrink-0" />
                      {t.entities.disconnect}
                    </Button>
                  </div>
                )}

                {/* Crypto wallet buttons */}
                {!missingIntegrations && isCryptoWallet && (
                  <div className="flex gap-2 flex-wrap justify-center w-full">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100"
                      onClick={onManage}
                      disabled={entityFetching || !onManage}
                    >
                      <Settings className="mr-1 h-4 w-4 flex-shrink-0" />
                      {t.entities.manage}
                    </Button>

                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-gray-900 font-bold hover:text-gray-700 dark:text-white dark:hover:text-gray-200"
                      disabled={entityFetching}
                      onClick={onSelect}
                    >
                      {entityFetching ? (
                        <>
                          <LoadingSpinner size="sm" />
                          <span className="ml-2 flex-shrink-0">
                            {t.common.fetching}
                          </span>
                        </>
                      ) : (
                        <>
                          <Download className="mr-2 h-4 w-4 flex-shrink-0" />
                          {getButtonText()}
                        </>
                      )}
                    </Button>
                  </div>
                )}
              </div>
            )}
        </CardContent>
      </Card>

      <ConfirmationDialog
        isOpen={showConfirmation}
        title={t.entities.confirmDisconnect}
        message={t.entities.confirmDisconnectMessage.replace(
          "{entity}",
          entity.name,
        )}
        confirmText={t.entities.disconnect}
        cancelText={t.common.cancel}
        onConfirm={confirmDisconnect}
        onCancel={cancelDisconnect}
      />
      <ConfirmationDialog
        isOpen={showExternalConfirmation}
        title={t.entities.confirmDisconnect}
        message={t.entities.confirmDisconnectMessage.replace(
          "{entity}",
          entity.name,
        )}
        confirmText={t.entities.disconnect}
        cancelText={t.common.cancel}
        onConfirm={confirmExternalDisconnect}
        onCancel={() => setShowExternalConfirmation(false)}
        isLoading={externalDisconnectLoading}
      />
      <ConfirmationDialog
        isOpen={showRelinkConfirmation}
        title={t.entities.confirmRelink}
        message={t.entities.confirmRelinkMessage.replace(
          "{entity}",
          entity.name,
        )}
        confirmText={t.entities.relink}
        cancelText={t.common.cancel}
        onConfirm={confirmExternalRelink}
        onCancel={() => setShowRelinkConfirmation(false)}
        isLoading={relinkingLoading}
      />
    </>
  )
}
