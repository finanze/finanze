import { useAppContext } from "@/context/AppContext"
import { EntityCard } from "@/components/EntityCard"
import { LoginForm } from "@/components/LoginForm"
import { PinPad } from "@/components/PinPad"
import { FeatureSelector } from "@/components/FeatureSelector"
import { Button } from "@/components/ui/Button"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { useI18n } from "@/i18n"
import { motion, AnimatePresence } from "framer-motion"
import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import {
  RefreshCw,
  Settings,
  ExternalLink,
  FileSpreadsheet,
} from "lucide-react"
import { useNavigate } from "react-router-dom"
import { EntitySetupLoginType, EntityStatus } from "@/types"
import { ConfirmationDialog } from "@/components/ui/ConfirmationDialog"

export default function EntityIntegrationsPage() {
  const {
    entities,
    isLoading,
    selectedEntity,
    pinRequired,
    selectEntity,
    fetchEntities,
    runVirtualScrape,
    view,
    setView,
    virtualEnabled,
    startExternalLogin,
    externalLoginInProgress,
    disconnectEntity,
  } = useAppContext()

  const { t } = useI18n()
  const navigate = useNavigate()
  const [showVirtualConfirm, setShowVirtualConfirm] = useState(false)
  const [isVirtualScraping, setIsVirtualScraping] = useState(false)

  const connectedEntities =
    entities?.filter(
      entity =>
        entity.status === EntityStatus.CONNECTED ||
        entity.status === EntityStatus.REQUIRES_LOGIN,
    ) || []

  const unconnectedEntities =
    entities?.filter(entity => entity.status === EntityStatus.DISCONNECTED) ||
    []

  const handleEntitySelect = (entity: any) => {
    selectEntity(entity)

    if (!entity.is_real) {
      setShowVirtualConfirm(true)
    } else if (entity.status === EntityStatus.DISCONNECTED) {
      handleLogin(entity)
    } else if (entity.status === EntityStatus.REQUIRES_LOGIN) {
      handleLogin(entity)
    } else {
      setView("features")
    }
  }

  const handleRelogin = (entity: any) => {
    selectEntity(entity)
    handleLogin(entity)
  }

  const handleDisconnect = async (entity: any) => {
    await disconnectEntity(entity.id)
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
    try {
      setIsVirtualScraping(true)
      await runVirtualScrape()
    } catch (error) {
      console.error("Error running virtual scrape:", error)
    } finally {
      setIsVirtualScraping(false)
      setShowVirtualConfirm(false)
    }
  }

  const handleVirtualCancel = () => {
    setShowVirtualConfirm(false)
  }

  const handleBack = () => {
    setView("entities")
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
    <div className="space-y-6">
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
              {isLoading ? (
                <LoadingSpinner size="sm" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
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
            {(connectedEntities.length > 0 || virtualEnabled) && (
              <motion.div variants={item} className="space-y-4">
                <h2 className="text-xl font-semibold">
                  {t.entities.connected}
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {connectedEntities.map(entity => (
                    <EntityCard
                      key={entity.id}
                      entity={entity}
                      onSelect={() => handleEntitySelect(entity)}
                      onRelogin={() => handleRelogin(entity)}
                      onDisconnect={() => handleDisconnect(entity)}
                      isLoading={isLoading}
                    />
                  ))}
                  {virtualEnabled && (
                    <Card
                      className="cursor-pointer transition-all hover:shadow-md border-green-500"
                      onClick={() => setShowVirtualConfirm(true)}
                    >
                      <CardHeader className="pb-2">
                        <CardTitle className="flex items-center">
                          <FileSpreadsheet className="h-5 w-5 mr-2" />
                          {t.entities.userEntered}
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                          {t.entities.userEnteredDescription}
                        </p>
                        <Button
                          variant="outline"
                          className="w-full"
                          onClick={e => {
                            e.stopPropagation()
                            setShowVirtualConfirm(true)
                          }}
                        >
                          {t.entities.importData}
                        </Button>
                      </CardContent>
                    </Card>
                  )}
                </div>
              </motion.div>
            )}

            {unconnectedEntities.length > 0 && (
              <motion.div variants={item} className="space-y-4">
                <h2 className="text-xl font-semibold">
                  {t.entities.available}
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {unconnectedEntities.map(entity => (
                    <EntityCard
                      key={entity.id}
                      entity={entity}
                      onSelect={() => handleEntitySelect(entity)}
                      onRelogin={() => handleRelogin(entity)}
                      onDisconnect={() => handleDisconnect(entity)}
                      isLoading={isLoading}
                    />
                  ))}
                  {!virtualEnabled && (
                    <Card className="cursor-pointer transition-all hover:shadow-md border-gray-300 opacity-80">
                      <CardHeader className="pb-2">
                        <CardTitle className="flex items-center">
                          <FileSpreadsheet className="h-5 w-5 mr-2" />
                          {t.entities.userEntered}
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                          {t.entities.userEnteredAvailableDescription}
                        </p>
                        <Button
                          variant="outline"
                          className="w-full"
                          onClick={e => {
                            e.stopPropagation()
                            navigate("/settings")
                          }}
                          disabled={isLoading}
                        >
                          <Settings className="mr-2 h-4 w-4" />
                          {t.entities.setupUserEntered}
                        </Button>
                      </CardContent>
                    </Card>
                  )}
                </div>
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
              <FeatureSelector />
            )}
          </motion.div>
        )}

        {pinRequired && selectedEntity && (
          <motion.div
            key="pinpad"
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
              <PinPad />
            )}
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
    </div>
  )
}
