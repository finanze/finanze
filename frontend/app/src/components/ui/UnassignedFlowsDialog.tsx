import React, { useState, useEffect } from "react"
import { Button } from "@/components/ui/Button"
import { Switch } from "@/components/ui/Switch"
import { Label } from "@/components/ui/Label"
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter,
  CardDescription,
} from "@/components/ui/Card"
import { useI18n } from "@/i18n"

interface UnassignedFlowsDialogProps {
  isOpen: boolean
  onConfirm: (removeUnassignedFlows: boolean) => void
  onCancel: () => void
  isLoading?: boolean
}

export function UnassignedFlowsDialog({
  isOpen,
  onConfirm,
  onCancel,
  isLoading = false,
}: UnassignedFlowsDialogProps) {
  const { t } = useI18n()
  const [removeUnassignedFlows, setRemoveUnassignedFlows] = useState(true)

  // Reset state when dialog opens
  useEffect(() => {
    if (isOpen) {
      setRemoveUnassignedFlows(true)
    }
  }, [isOpen])

  if (!isOpen) return null

  const handleConfirm = () => {
    onConfirm(removeUnassignedFlows)
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-[10001]">
      <Card className="w-full max-w-md mx-4">
        <CardHeader>
          <CardTitle>
            {t.realEstate.modals.removeUnassignedFlowsTitle}
          </CardTitle>
          <CardDescription>
            {t.realEstate.modals.deleteUnassignedFlows}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
            <div className="flex-1">
              <Label
                htmlFor="remove-unassigned-flows"
                className="text-sm font-medium"
              >
                {t.realEstate.modals.removeUnassignedFlows}
              </Label>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                {t.realEstate.modals.deleteUnassignedFlows}
              </p>
            </div>
            <Switch
              id="remove-unassigned-flows"
              checked={removeUnassignedFlows}
              onCheckedChange={setRemoveUnassignedFlows}
              disabled={isLoading}
            />
          </div>
        </CardContent>
        <CardFooter className="flex justify-end gap-2">
          <Button variant="outline" onClick={onCancel} disabled={isLoading}>
            {t.common.cancel}
          </Button>
          <Button onClick={handleConfirm} disabled={isLoading}>
            {isLoading ? (
              <div className="flex items-center">
                <span>{t.common.loading}</span>
              </div>
            ) : (
              t.common.confirm
            )}
          </Button>
        </CardFooter>
      </Card>
    </div>
  )
}
