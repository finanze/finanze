import * as React from "react"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"
import { createPortal } from "react-dom"
import { motion } from "framer-motion"

interface ToastProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "success" | "warning" | "error"
  onClose?: () => void
  isAnimating?: boolean
}

const Toast = React.forwardRef<HTMLDivElement, ToastProps>(
  (
    {
      className,
      variant = "success",
      onClose,
      children,
      isAnimating,
      ...props
    },
    ref,
  ) => {
    const toastContent = (
      <div
        ref={ref}
        className={cn(
          "fixed bottom-4 right-4 left-4 sm:left-auto z-[10050] flex max-w-md items-center justify-between space-x-4 overflow-hidden rounded-md border p-6 pr-8 shadow-lg transition-all backdrop-blur-sm",
          {
            "success group border-green-200 bg-green-50 text-green-900 dark:bg-green-900 dark:border-green-800 dark:text-green-100":
              variant === "success",
            "error group border-destructive bg-destructive text-destructive-foreground":
              variant === "error",
            "warning group border-amber-500 bg-amber-50 text-amber-900 dark:bg-amber-900 dark:border-amber-800 dark:text-amber-100":
              variant === "warning",
          },
          className,
        )}
        {...props}
      >
        <div className="flex-1">{children}</div>
        {onClose && (
          <button
            onClick={onClose}
            className="rounded-full p-1 text-foreground transition-opacity hover:text-foreground hover:opacity-100 focus:opacity-100 focus:outline-none focus:ring-2 group-[.error]:text-red-200 group-[.error]:hover:text-red-50 group-[.error]:focus:ring-red-400 group-[.error]:focus:ring-offset-red-600 group-[.warning]:text-amber-900 group-[.warning]:hover:text-amber-950 group-[.warning]:focus:ring-amber-400 group-[.success]:text-green-900 group-[.success]:hover:text-green-950 group-[.success]:focus:ring-green-400"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
    )

    if (isAnimating) {
      return typeof document !== "undefined"
        ? createPortal(
            <motion.div
              initial={{ opacity: 0, y: 50 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 50 }}
              transition={{ type: "spring", stiffness: 500, damping: 30 }}
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
