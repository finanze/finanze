import { useState, useEffect, useCallback, useRef } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { ArrowRight, Delete, X } from "lucide-react"
import { useEntityWorkflow } from "@/context/EntityWorkflowContext"
import { useI18n } from "@/i18n"
import { Button } from "@/components/ui/Button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { ConfirmationDialog } from "@/components/ui/ConfirmationDialog"

export function PinPad() {
  const {
    selectedEntity,
    pinLength,
    currentAction,
    login,
    scrape,
    storedCredentials,
    selectedFeatures,
    fetchOptions,
    pinError,
    clearPinError,
    fetchingEntityState,
    resetState,
    setView,
    getPendingScrapeParams,
    clearPendingScrapeParams,
    switchActivePinEntity,
    getPendingPinEntities,
  } = useEntityWorkflow()
  const pinByEntityRef = useRef<Map<string, string[]>>(new Map())
  const [pin, setPin] = useState<string[]>([])
  const [showCancelDialog, setShowCancelDialog] = useState(false)
  const { t } = useI18n()

  if (!selectedEntity) return null

  const isEntityFetching = fetchingEntityState.fetchingEntityIds.includes(
    selectedEntity.id,
  )
  const pendingEntities = getPendingPinEntities()
  const idsRequiringCode = [
    selectedEntity.id,
    ...pendingEntities.map(p => p.id),
  ]
  const allRequiringAreFetching = idsRequiringCode.every(id =>
    fetchingEntityState.fetchingEntityIds.includes(id),
  )
  const isBackgroundFetch =
    currentAction === "scrape" && isEntityFetching && allRequiringAreFetching
  const cancelButtonLabel = isBackgroundFetch
    ? t.common.continueInBackground
    : t.common.cancel
  const cancelMessage =
    currentAction === "scrape"
      ? t.pinpad.cancelFetchDescription
      : t.pinpad.cancelLoginDescription

  const syncPinForEntity = useCallback(
    (nextPin: string[]) => {
      setPin(nextPin)
      if (selectedEntity) {
        pinByEntityRef.current.set(selectedEntity.id, nextPin)
      }
    },
    [selectedEntity],
  )

  useEffect(() => {
    if (!selectedEntity) return
    const storedPin = pinByEntityRef.current.get(selectedEntity.id)
    setPin(storedPin ?? [])
  }, [selectedEntity])

  useEffect(() => {
    if (pinError) {
      syncPinForEntity([])
      clearPinError()
    }
  }, [pinError, clearPinError, syncPinForEntity])

  const handleNumberClick = (num: string) => {
    if (pin.length < pinLength) {
      syncPinForEntity([...pin, num])
    }
  }

  const handleClear = () => {
    syncPinForEntity([])
  }

  const handleDelete = () => {
    if (pin.length > 0) {
      syncPinForEntity(pin.slice(0, -1))
    }
  }

  const handleSubmit = () => {
    const pinString = pin.join("")

    if (currentAction === "login" && storedCredentials) {
      login(storedCredentials, pinString)
    } else if (currentAction === "scrape" && selectedEntity) {
      const pendingParams = getPendingScrapeParams(selectedEntity.id)
      const featuresToUse = pendingParams?.features ?? selectedFeatures
      const optionsToUse = pendingParams?.options ?? fetchOptions

      scrape(selectedEntity, featuresToUse, {
        code: pinString,
        deep: optionsToUse.deep,
        avoidNewLogin: optionsToUse.avoidNewLogin,
      })
    }
  }

  const handleCancelRequest = () => {
    if (isBackgroundFetch) {
      handleCancelConfirm()
      return
    }
    setShowCancelDialog(true)
  }

  const handleCancelConfirm = () => {
    setShowCancelDialog(false)

    if (isBackgroundFetch) {
      pinByEntityRef.current.clear()
      resetState()
      setView("entities")
      return
    }

    if (selectedEntity) {
      pinByEntityRef.current.delete(selectedEntity.id)
      clearPendingScrapeParams(selectedEntity.id)
    }

    const remaining = getPendingPinEntities()
    if (remaining.length > 0) {
      switchActivePinEntity(remaining[0].id)
      return
    }

    resetState()
    setView("entities")
  }

  const handleCancelDismiss = () => {
    setShowCancelDialog(false)
  }

  const handleKeyboardInput = useCallback(
    (e: KeyboardEvent) => {
      // Avoid capturing when typing inside inputs/textareas or editable elements
      const target = e.target as HTMLElement | null
      if (target) {
        const tag = target.tagName
        if (tag === "INPUT" || tag === "TEXTAREA" || target.isContentEditable) {
          return
        }
      }

      if (isEntityFetching) return

      const { key } = e
      if (/^[0-9]$/.test(key)) {
        if (pin.length < pinLength) {
          syncPinForEntity([...pin, key])
        }
        return
      }

      if (key === "Backspace" || key === "Delete") {
        if (pin.length > 0) syncPinForEntity(pin.slice(0, -1))
        return
      }

      if (key === "Escape") {
        syncPinForEntity([])
        return
      }

      if (key === "Enter") {
        if (pin.length === pinLength) {
          handleSubmit()
        }
      }
    },
    [pin, pinLength, handleSubmit, isEntityFetching, syncPinForEntity],
  )

  useEffect(() => {
    window.addEventListener("keydown", handleKeyboardInput)
    return () => window.removeEventListener("keydown", handleKeyboardInput)
  }, [handleKeyboardInput])

  const enterCodeText = t.pinpad.enterCode.replace(
    "{length}",
    pinLength.toString(),
  )
  const pendingBannerText =
    pendingEntities.length === 1
      ? t.pinpad.switchToEntity.replace("{entity}", pendingEntities[0].name)
      : t.pinpad.pendingRequests

  return (
    <Card className="mx-auto w-full max-w-md">
      <CardHeader>
        <CardTitle className="text-center">
          {enterCodeText} {selectedEntity.name}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {pendingEntities.length > 0 && (
          <div className="mb-4 rounded-lg border border-blue-200/60 bg-blue-50 px-3 py-3 text-xs text-blue-900 dark:border-blue-400/40 dark:bg-blue-500/10 dark:text-blue-50 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <span className="leading-snug sm:flex-1 sm:max-w-none">
              {pendingBannerText}
            </span>
            <div className="flex flex-wrap gap-2">
              {pendingEntities.map(entry => (
                <Button
                  key={entry.id}
                  variant="outline"
                  size="sm"
                  className="h-8 px-3 text-xs"
                  onClick={() => switchActivePinEntity(entry.id)}
                >
                  {t.pinpad.switchToEntity.replace("{entity}", entry.name)}
                </Button>
              ))}
            </div>
          </div>
        )}

        <div className="flex justify-center mb-6">
          {Array.from({ length: pinLength }).map((_, index) => (
            <div
              key={index}
              className={`w-3 h-3 mx-1 rounded-full ${
                index < pin.length
                  ? "bg-primary"
                  : "border border-gray-300 dark:border-gray-700"
              }`}
            />
          ))}
        </div>

        <AnimatePresence>
          {pinError && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="mb-4 text-center text-red-500 dark:text-red-400 text-sm"
            >
              {t.errors.INVALID_CODE}
            </motion.div>
          )}
        </AnimatePresence>

        <div className="grid grid-cols-3 gap-3">
          {[1, 2, 3, 4, 5, 6, 7, 8, 9].map(num => (
            <Button
              key={num}
              variant="ghost"
              className="h-14 text-lg rounded-full hover:bg-gray-100 dark:hover:bg-gray-900"
              onClick={() => handleNumberClick(num.toString())}
            >
              {num}
            </Button>
          ))}
          <Button
            variant="ghost"
            className="h-14 rounded-full hover:bg-gray-100 dark:hover:bg-gray-900"
            onClick={handleClear}
          >
            <X className="h-5 w-5" />
          </Button>
          <Button
            variant="ghost"
            className="h-14 text-lg rounded-full hover:bg-gray-100 dark:hover:bg-gray-900"
            onClick={() => handleNumberClick("0")}
          >
            0
          </Button>
          <Button
            variant="ghost"
            className="h-14 rounded-full hover:bg-gray-100 dark:hover:bg-gray-900"
            onClick={handleDelete}
          >
            <Delete className="h-5 w-5" />
          </Button>
        </div>

        <div className="mt-6 flex gap-2">
          <Button
            variant="outline"
            className="flex-1"
            onClick={handleCancelRequest}
          >
            <X className="mr-2 h-4 w-4" />
            {allRequiringAreFetching ? cancelButtonLabel : t.common.cancel}
          </Button>
          <Button
            className="flex-1"
            disabled={pin.length < pinLength || isEntityFetching}
            onClick={handleSubmit}
          >
            <ArrowRight className="mr-2 h-4 w-4" />
            {isEntityFetching ? t.common.fetching : t.common.submit}
          </Button>
        </div>

        <div className="mt-3 text-center text-xs text-muted-foreground">
          {t.pinpad.codeDelayTip}
        </div>
      </CardContent>
      <ConfirmationDialog
        isOpen={showCancelDialog}
        title={t.pinpad.cancelConfirmationTitle}
        message={cancelMessage}
        confirmText={t.common.confirm}
        cancelText={t.common.cancel}
        onConfirm={handleCancelConfirm}
        onCancel={handleCancelDismiss}
      />
    </Card>
  )
}
