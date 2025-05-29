import { useState } from "react"

import type { Entity } from "@/types"
import { EntityStatus } from "@/types"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardFooter,
} from "@/components/ui/Card"
import { Badge } from "@/components/ui/Badge"
import { Button } from "@/components/ui/Button"
import { useI18n } from "@/i18n"
import { RefreshCw, Trash2 } from "lucide-react"
import { ConfirmationDialog } from "@/components/ui/ConfirmationDialog"

interface EntityCardProps {
  entity: Entity
  onSelect: () => void
  onRelogin: () => void
  onDisconnect: () => void
  isLoading: boolean
}

export function EntityCard({
  entity,
  onSelect,
  onRelogin,
  onDisconnect,
  isLoading,
}: EntityCardProps) {
  const { t } = useI18n()
  const [showConfirmation, setShowConfirmation] = useState(false)

  // Determine card styling based on entity status
  const getCardStyle = () => {
    switch (entity.status) {
      case EntityStatus.CONNECTED:
        return "border-green-500"
      case EntityStatus.REQUIRES_LOGIN:
        return "border-amber-500"
      default:
        return "border-gray-300 opacity-80"
    }
  }

  // Determine badge styling and text based on entity status
  const getBadgeInfo = () => {
    switch (entity.status) {
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

  // Determine button text based on entity status
  const getButtonText = () => {
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

  const cancelDisconnect = () => {
    setShowConfirmation(false)
  }

  const badgeInfo = getBadgeInfo()
  const isConnectedOrRequiresLogin =
    entity.status === EntityStatus.CONNECTED ||
    entity.status === EntityStatus.REQUIRES_LOGIN

  return (
    <>
      <Card className={`transition-all hover:shadow-md ${getCardStyle()}`}>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center">
              <div className="w-10 h-10 mr-3 flex-shrink-0 overflow-hidden rounded-md">
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
              <span>{entity.name}</span>
            </div>
            {badgeInfo && (
              <Badge variant="outline" className={badgeInfo.style}>
                {badgeInfo.text}
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-1 mt-2">
            {entity.features.map(feature => (
              <Badge key={feature} variant="secondary" className="text-xs">
                {t.features[feature]}
              </Badge>
            ))}
          </div>
          <Button
            variant={
              entity.status !== EntityStatus.DISCONNECTED
                ? "default"
                : "outline"
            }
            className="w-full mt-4"
            disabled={isLoading}
            onClick={onSelect}
          >
            {getButtonText()}
          </Button>
        </CardContent>
        {isConnectedOrRequiresLogin && (
          <CardFooter className="flex justify-between p-2 pt-0">
            {entity.status === EntityStatus.CONNECTED && (
              <Button
                variant="ghost"
                size="sm"
                className="text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100"
                onClick={onRelogin}
                disabled={isLoading}
              >
                <RefreshCw size={16} className="mr-1" />
                {t.entities.relogin}
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              className="text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300 ml-auto"
              onClick={handleDisconnect}
              disabled={isLoading}
            >
              <Trash2 size={16} className="mr-1" />
              {t.entities.disconnect}
            </Button>
          </CardFooter>
        )}
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
