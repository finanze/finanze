import * as React from "react"
import { X, CheckCircle2, AlertCircle, AlertTriangle, Info } from "lucide-react"
import { cn } from "@/lib/utils"
import { createPortal } from "react-dom"
import { motion } from "framer-motion"

interface ToastProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "success" | "warning" | "error" | "info"
  onClose?: () => void
  isAnimating?: boolean
  bottomOffsetClassName?: string
}

const variantConfig = {
  success: {
    icon: CheckCircle2,
    iconClass: "text-emerald-500",
    accentClass: "border-l-emerald-500",
  },
  error: {
    icon: AlertCircle,
    iconClass: "text-red-500",
    accentClass: "border-l-red-500",
  },
  warning: {
    icon: AlertTriangle,
    iconClass: "text-amber-500",
    accentClass: "border-l-amber-500",
  },
  info: {
    icon: Info,
    iconClass: "text-muted-foreground",
    accentClass: "border-l-border",
  },
}

const Toast = React.forwardRef<HTMLDivElement, ToastProps>(
  (
    {
      className,
      variant = "success",
      onClose,
      children,
      isAnimating,
      bottomOffsetClassName,
      ...props
    },
    ref,
  ) => {
    const { icon: Icon, iconClass, accentClass } = variantConfig[variant]

    const toastContent = (
      <div
        ref={ref}
        className={cn(
          "fixed bottom-4 right-4 left-4 sm:left-auto z-[10050] flex max-w-sm items-start gap-3 overflow-hidden rounded-lg border border-l-[4px] border-border bg-background/95 px-4 py-3.5 shadow-md backdrop-blur-md transition-all",
          accentClass,
          bottomOffsetClassName,
          className,
        )}
        {...props}
      >
        <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", iconClass)} />
        <div className="flex-1 text-sm text-foreground leading-snug">
          {children}
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="ml-1 shrink-0 rounded p-0.5 text-muted-foreground transition-colors hover:text-foreground focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
    )

    if (isAnimating) {
      return typeof document !== "undefined"
        ? createPortal(
            <motion.div
              initial={{ opacity: 0, y: 8, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.97 }}
              transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            >
              {toastContent}
            </motion.div>,
            document.body,
          )
        : toastContent
    }

    return typeof document !== "undefined"
      ? createPortal(toastContent, document.body)
      : toastContent
  },
)
Toast.displayName = "Toast"

export { Toast }
