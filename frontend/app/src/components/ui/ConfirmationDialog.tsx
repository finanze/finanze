import { Button } from '@/components/ui/Button'
import {
    Card,
    CardHeader,
    CardTitle,
    CardContent,
    CardFooter,
    CardDescription,
} from '@/components/ui/Card'
import { useI18n } from '@/i18n'

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
}: ConfirmationDialogProps) {
    const { t } = useI18n() // Added hook usage
    if (!isOpen) return null

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
            <Card className="w-full max-w-md mx-4">
                <CardHeader>
                    <CardTitle>{title}</CardTitle>
                    {description && (
                        <CardDescription>{description}</CardDescription>
                    )}
                </CardHeader>
                <CardContent>
                    <p>{message}</p>
                </CardContent>
                <CardFooter className="flex justify-end gap-2">
                    <Button
                        variant="outline"
                        onClick={onCancel}
                        disabled={isLoading}
                    >
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
