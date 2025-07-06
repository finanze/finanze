import { useState } from "react"

import type { Entity } from "@/types"
import { EntityStatus, EntityType } from "@/types"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { Badge } from "@/components/ui/Badge"
import { Button } from "@/components/ui/Button"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { FeaturesBadge } from "@/components/ui/FeaturesBadge"
import { useAppContext } from "@/context/AppContext"
import { useI18n } from "@/i18n"
import {
  RefreshCw,
  Trash2,
  Settings,
  Wallet,
  Download,
  LogIn,
} from "lucide-react"
import { ConfirmationDialog } from "@/components/ui/ConfirmationDialog"

interface EntityCardProps {
  entity: Entity
  onSelect: () => void
  onRelogin: () => void
  onDisconnect: () => void
  onManage?: () => void
}

export function EntityCard({
  entity,
  onSelect,
  onRelogin,
  onDisconnect,
  onManage,
}: EntityCardProps) {
  const { t } = useI18n()
  const { fetchingEntityState } = useAppContext()
  const [showConfirmation, setShowConfirmation] = useState(false)

  const { fetchingEntityIds } = fetchingEntityState

  // Check if this entity is currently being fetched
  const entityFetching = fetchingEntityIds.includes(entity.id)

  // Helper function to determine if a crypto wallet entity is connected
  const isCryptoWalletConnected = () => {
    return (
      entity.type === EntityType.CRYPTO_WALLET &&
      entity.connected &&
      entity.connected.length > 0
    )
  }

  // Helper function to get effective status for crypto wallets
  const getEffectiveStatus = () => {
    if (entity.type === EntityType.CRYPTO_WALLET) {
      return isCryptoWalletConnected()
        ? EntityStatus.CONNECTED
        : EntityStatus.DISCONNECTED
    }
    return entity.status
  }

  const effectiveStatus = getEffectiveStatus()

  // Determine card styling based on effective entity status
  const getCardStyle = () => {
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
    switch (effectiveStatus) {
      case EntityStatus.CONNECTED:
        return {
          style:
            "bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-300",
          text: t.entities.connected,
        }
      case EntityStatus.REQUIRES_LOGIN:
        return {
          style:
            "bg-amber-100 text-amber-800 dark:bg-amber-900/20 dark:text-amber-300",
          text: t.entities.requiresLogin,
        }
      default:
        return null
    }
  }

  // Determine button text based on entity type and status
  const getButtonText = () => {
    if (entity.type === EntityType.CRYPTO_WALLET) {
      return effectiveStatus === EntityStatus.CONNECTED
        ? "Fetch"
        : t.entities.connect
    }

    switch (entity.status) {
      case EntityStatus.CONNECTED:
        return "Fetch"
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

  const cancelDisconnect = () => {
    setShowConfirmation(false)
  }

  const badgeInfo = getBadgeInfo()

  const isFinancialInstitution =
    entity.type === EntityType.FINANCIAL_INSTITUTION
  const isCryptoWallet = entity.type === EntityType.CRYPTO_WALLET

  const isDisconnected = effectiveStatus === EntityStatus.DISCONNECTED

  return (
    <>
      <Card
        className={`transition-all hover:shadow-md ${getCardStyle()} ${
          isDisconnected ? "cursor-pointer hover:opacity-100" : ""
        }`}
        onClick={isDisconnected ? onSelect : undefined}
      >
        <CardHeader className={isDisconnected ? "pb-0" : "pb-2"}>
          <CardTitle className="flex items-center justify-between gap-2 flex-wrap">
            <div className="flex items-center min-w-0">
              <div
                className={`${isDisconnected ? "w-8 h-8 mr-2" : "w-10 h-10 mr-3"} flex-shrink-0 overflow-hidden rounded-md`}
              >
                <img
                  src={`entities/${entity.id}.png`}
                  alt={`${entity.name} logo`}
                  className="w-full h-full object-contain"
                  onError={e => {
                    // If image fails to load, hide it
                    ;(e.target as HTMLImageElement).style.display = "none"
                  }}
                />
              </div>
              <span className="truncate">{entity.name}</span>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <FeaturesBadge features={entity.features} />
              {badgeInfo && (
                <Badge
                  variant="outline"
                  className={`${badgeInfo.style} ${isDisconnected ? "text-xs py-0" : ""}`}
                >
                  {badgeInfo.text}
                </Badge>
              )}
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

          {/* Show fetch button only for entities requiring login */}
          {effectiveStatus === EntityStatus.REQUIRES_LOGIN && (
            <Button
              variant="ghost"
              size="sm"
              className={`w-full mt-4 h-9 text-gray-900 font-bold hover:text-gray-700 dark:text-white dark:hover:text-gray-200`}
              disabled={entityFetching}
              onClick={onSelect}
            >
              {entityFetching ? (
                <>
                  <LoadingSpinner size="sm" />
                  <span className="ml-2">{t.common.fetching}</span>
                </>
              ) : (
                <>
                  <LogIn className="mr-2 h-4 w-4" />
                  {getButtonText()}
                </>
              )}
            </Button>
          )}

          {/* Show loading fetch button for connected entities when fetching */}
          {effectiveStatus === EntityStatus.CONNECTED && entityFetching && (
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

          {/* Button row for connected entities - buttons surrounding the fetch button */}
          {effectiveStatus === EntityStatus.CONNECTED && !entityFetching && (
            <div className="flex flex-wrap gap-2 mt-4">
              {/* Financial institution buttons */}
              {isFinancialInstitution && (
                <>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="flex-1 min-w-0 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100"
                    onClick={onRelogin}
                    disabled={entityFetching}
                  >
                    <RefreshCw className="mr-1 h-4 w-4 flex-shrink-0" />
                    {t.entities.relogin}
                  </Button>

                  <Button
                    variant="ghost"
                    size="sm"
                    className="flex-[1.5] min-w-0 text-gray-900 font-bold hover:text-gray-700 dark:text-white dark:hover:text-gray-200"
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

                  <Button
                    variant="ghost"
                    size="sm"
                    className="flex-1 min-w-0 text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300"
                    onClick={handleDisconnect}
                    disabled={entityFetching}
                  >
                    <Trash2 className="mr-1 h-4 w-4 flex-shrink-0" />
                    {t.entities.disconnect}
                  </Button>
                </>
              )}

              {/* Crypto wallet buttons */}
              {isCryptoWallet && (
                <>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="flex-1 min-w-0 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100"
                    onClick={onManage}
                    disabled={entityFetching || !onManage}
                  >
                    <Settings className="mr-1 h-4 w-4 flex-shrink-0" />
                    {t.entities.manage}
                  </Button>

                  <Button
                    variant="ghost"
                    size="sm"
                    className="flex-[1.5] min-w-0 text-gray-900 font-bold hover:text-gray-700 dark:text-white dark:hover:text-gray-200"
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
    </>
  )
}
