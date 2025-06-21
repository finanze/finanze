import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter,
} from "@/components/ui/Card"

interface EditDialogProps {
  isOpen: boolean
  title: string
  value: string
  onValueChange: (value: string) => void
  confirmText: string
  cancelText: string
  onConfirm: () => void
  onCancel: () => void
  isLoading?: boolean
  placeholder?: string
}

export function EditDialog({
  isOpen,
  title,
  value,
  onValueChange,
  confirmText,
  cancelText,
  onConfirm,
  onCancel,
  isLoading = false,
  placeholder,
}: EditDialogProps) {
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <Card className="w-full max-w-md mx-4">
        <CardHeader>
          <CardTitle>{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <Input
            value={value}
            onChange={e => onValueChange(e.target.value)}
            placeholder={placeholder}
            disabled={isLoading}
            autoFocus
          />
        </CardContent>
        <CardFooter className="flex justify-end gap-2">
          <Button variant="outline" onClick={onCancel} disabled={isLoading}>
            {cancelText}
          </Button>
          <Button onClick={onConfirm} disabled={isLoading}>
            {confirmText}
          </Button>
        </CardFooter>
      </Card>
    </div>
  )
}
