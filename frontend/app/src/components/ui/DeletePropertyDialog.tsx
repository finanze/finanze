import React, { useState } from "react"
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

interface DeletePropertyDialogProps {
  isOpen: boolean
  propertyName: string
  onConfirm: (removeRelatedFlows: boolean) => void
  onCancel: () => void
  isLoading?: boolean
}

export function DeletePropertyDialog({
  isOpen,
  propertyName,
  onConfirm,
  onCancel,
  isLoading = false,
}: DeletePropertyDialogProps) {
  const { t } = useI18n()
  const [removeRelatedFlows, setRemoveRelatedFlows] = useState(true)

  if (!isOpen) return null

  const handleConfirm = () => {
    onConfirm(removeRelatedFlows)
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-[10001]">
      <Card className="w-full max-w-md mx-4">
        <CardHeader>
          <CardTitle>{t.realEstate.deleteProperty}</CardTitle>
          <CardDescription>{t.realEstate.modals.deleteConfirm}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            <strong>{propertyName}</strong>
          </p>

          <div className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
            <div className="flex-1">
              <Label htmlFor="remove-flows" className="text-sm font-medium">
                {t.realEstate.modals.removeRelatedFlows}
              </Label>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                {t.realEstate.modals.removeRelatedFlowsDescription}
              </p>
            </div>
            <Switch
              id="remove-flows"
              checked={removeRelatedFlows}
              onCheckedChange={setRemoveRelatedFlows}
              disabled={isLoading}
            />
          </div>
        </CardContent>
        <CardFooter className="flex justify-end gap-2">
          <Button variant="outline" onClick={onCancel} disabled={isLoading}>
            {t.common.cancel}
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={isLoading}
            variant="destructive"
          >
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
