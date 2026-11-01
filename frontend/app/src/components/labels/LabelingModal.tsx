import { type ReactNode } from "react"
import { createPortal } from "react-dom"
import { AnimatePresence, motion } from "framer-motion"
import { X } from "lucide-react"
import { Button } from "@/components/ui/Button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card"
import { useModalBackHandler } from "@/hooks/useModalBackHandler"
import { useI18n } from "@/i18n"
import { cn } from "@/lib/utils"

interface LabelingModalProps {
  isOpen: boolean
  title: string
  description?: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  headerAction?: ReactNode
  className?: string
  testId?: string
}

export function LabelingModal({
  isOpen,
  title,
  description,
  onClose,
  children,
  footer,
  headerAction,
  className,
  testId,
}: LabelingModalProps) {
  const { t } = useI18n()
  useModalBackHandler(isOpen, onClose)

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 z-[18000] flex items-center justify-center bg-black/50 px-3 pb-4 pt-10 sm:px-4"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className={cn("w-full max-w-lg", className)}
            data-testid={testId}
            role="dialog"
            aria-modal="true"
          >
            <Card className="flex max-h-[calc(100vh-5rem)] flex-col">
              <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0 p-4 sm:p-6">
                <div className="space-y-1">
                  <CardTitle className="text-xl">{title}</CardTitle>
                  {description && (
                    <CardDescription>{description}</CardDescription>
                  )}
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {headerAction}
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={onClose}
                    aria-label={t.common.close}
                    className="h-8 w-8 shrink-0"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="flex-1 space-y-4 overflow-y-auto px-4 pb-4 sm:px-6 sm:pb-6">
                {children}
              </CardContent>
              {footer && (
                <CardFooter className="flex flex-wrap justify-end gap-2 px-4 pb-4 sm:px-6 sm:pb-6">
                  {footer}
                </CardFooter>
              )}
            </Card>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  )
}
