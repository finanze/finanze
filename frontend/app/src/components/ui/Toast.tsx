import * as React from "react"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"

interface ToastProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "destructive" | "warning"
  onClose?: () => void
}

const Toast = React.forwardRef<HTMLDivElement, ToastProps>(
  ({ className, variant = "default", onClose, children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "fixed bottom-4 right-4 z-50 flex max-w-md items-center justify-between space-x-4 overflow-hidden rounded-md border p-6 pr-8 shadow-lg transition-all data-[state=open]:animate-in data-[state=closed]:animate-out data-[swipe=end]:animate-out data-[state=closed]:fade-out-80 data-[state=open]:slide-in-from-top-full data-[state=open]:slide-in-from-right-full data-[state=closed]:slide-out-to-right-full",
          {
            "border-border bg-background text-foreground": variant === "default",
            "destructive group border-destructive bg-destructive text-destructive-foreground":
              variant === "destructive",
            "warning group border-amber-500 bg-amber-50 text-amber-800 dark:bg-amber-900/20 dark:border-amber-800 dark:text-amber-300":
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
            className="rounded-full p-1 text-foreground/50 opacity-70 transition-opacity hover:text-foreground hover:opacity-100 focus:opacity-100 focus:outline-none focus:ring-2 group-[.destructive]:text-red-300 group-[.destructive]:hover:text-red-50 group-[.destructive]:focus:ring-red-400 group-[.destructive]:focus:ring-offset-red-600 group-[.warning]:text-amber-800 group-[.warning]:hover:text-amber-900 group-[.warning]:focus:ring-amber-400"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
    )
  },
)
Toast.displayName = "Toast"

export { Toast }
