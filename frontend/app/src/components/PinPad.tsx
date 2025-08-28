import { useState, useEffect, useCallback } from "react"
import { useAppContext } from "@/context/AppContext"
import { Button } from "@/components/ui/Button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { X, ArrowRight, Delete } from "lucide-react"
import { useI18n } from "@/i18n"
import { motion, AnimatePresence } from "framer-motion"

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
  } = useAppContext()
  const [pin, setPin] = useState<string[]>([])
  const { t } = useI18n()

  if (!selectedEntity) return null

  const isEntityFetching = fetchingEntityState.fetchingEntityIds.includes(
    selectedEntity.id,
  )

  useEffect(() => {
    // Reset PIN when component mounts
    setPin([])
  }, [])

  useEffect(() => {
    if (pinError) {
      setPin([])
      clearPinError()
    }
  }, [pinError, clearPinError])

  if (!selectedEntity) return null

  const handleNumberClick = (num: string) => {
    if (pin.length < pinLength) {
      setPin([...pin, num])
    }
  }

  const handleClear = () => {
    setPin([])
  }

  const handleDelete = () => {
    if (pin.length > 0) {
      setPin(pin.slice(0, -1))
    }
  }

  const handleSubmit = () => {
    const pinString = pin.join("")

    if (currentAction === "login" && storedCredentials) {
      login(storedCredentials, pinString)
    } else if (currentAction === "scrape") {
      scrape(selectedEntity, selectedFeatures, {
        code: pinString,
        deep: fetchOptions.deep,
      })
    }

    // Don't reset PIN - we'll handle it based on response
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
          setPin(prev => [...prev, key])
        }
        return
      }

      if (key === "Backspace" || key === "Delete") {
        if (pin.length > 0) setPin(prev => prev.slice(0, -1))
        return
      }

      if (key === "Escape") {
        setPin([])
        return
      }

      if (key === "Enter") {
        if (pin.length === pinLength) {
          handleSubmit()
        }
      }
    },
    [pin, pinLength, handleSubmit, isEntityFetching],
  )

  useEffect(() => {
    window.addEventListener("keydown", handleKeyboardInput)
    return () => window.removeEventListener("keydown", handleKeyboardInput)
  }, [handleKeyboardInput])

  const enterCodeText = t.pinpad.enterCode.replace(
    "{length}",
    pinLength.toString(),
  )

  return (
    <Card className="w-full max-w-md mx-auto">
      <CardHeader>
        <CardTitle className="text-center">
          {enterCodeText} {selectedEntity.name}
        </CardTitle>
      </CardHeader>
      <CardContent>
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

        <Button
          className="w-full mt-6"
          disabled={pin.length < pinLength || isEntityFetching}
          onClick={handleSubmit}
        >
          <ArrowRight className="mr-2 h-4 w-4" />
          {isEntityFetching ? t.common.fetching : t.common.submit}
        </Button>

        <div className="mt-3 text-center text-xs text-muted-foreground">
          {t.pinpad.codeDelayTip}
        </div>
      </CardContent>
    </Card>
  )
}
