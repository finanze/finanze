import { Button } from "@/components/ui/Button"
import { AlertTriangle } from "lucide-react"
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter,
  CardDescription,
} from "@/components/ui/Card"
import { useI18n } from "@/i18n"

interface ConfirmationDialogProps {
  isOpen: boolean
  title: string
  message: string
  confirmText: string
  cancelText: string
  onConfirm: () => void
  onCancel: () => void
  isLoading?: boolean
  description?: string
  warning?: string
}

export function ConfirmationDialog({
  isOpen,
  title,
  message,
  confirmText,
  cancelText,
  onConfirm,
  onCancel,
  isLoading = false,
  description,
  warning,
}: ConfirmationDialogProps) {
  const { t } = useI18n() // Added hook usage
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-[18000]">
      <Card className="w-full max-w-md mx-4">
        <CardHeader>
          <CardTitle>{title}</CardTitle>
          {description && <CardDescription>{description}</CardDescription>}
        </CardHeader>
        <CardContent>
          <p>{message}</p>
          {warning && (
            <div className="mt-3 flex items-start gap-2 pl-3 border-l-2 border-yellow-500/60 text-yellow-700 dark:text-yellow-400">
              <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
              <div>
                <div className="font-medium">{t.common.warning}</div>
                {warning
                  .split(/\n+/)
                  .map(part => part.trim())
                  .filter(Boolean)
                  .map((message, index) => (
                    <p
                      key={`${message}-${index}`}
                      className="text-sm opacity-90"
                    >
                      {message}
                    </p>
                  ))}
              </div>
            </div>
          )}
        </CardContent>
        <CardFooter className="flex justify-end gap-2">
          <Button variant="outline" onClick={onCancel} disabled={isLoading}>
            {cancelText}
          </Button>
          <Button onClick={onConfirm} disabled={isLoading}>
            {isLoading ? (
              <div className="flex items-center">
                <span>{t.common.loading}</span>
              </div>
            ) : (
              confirmText
            )}
          </Button>
        </CardFooter>
      </Card>
    </div>
  )
}
