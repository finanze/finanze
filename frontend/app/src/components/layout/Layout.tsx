import type React from "react"
import { Sidebar } from "./Sidebar"
import { Toast } from "@/components/ui/Toast"
import { useAppContext } from "@/context/AppContext"
import { motion, AnimatePresence } from "framer-motion"
import { PlatformType } from "@/types"
import { useI18n } from "@/i18n"

interface LayoutProps {
  children: React.ReactNode
}

export function Layout({ children }: LayoutProps) {
  const { toast, hideToast, platform } = useAppContext()
  const { t } = useI18n()

  return (
    <div className="flex h-screen min-h-0 overflow-hidden bg-gray-50 dark:bg-black text-gray-900 dark:text-gray-100">
      <Sidebar />
      {/* Titlebar control buttons */}
      <main
        className={`flex-1 min-h-0 overflow-auto ${
          platform === PlatformType.WINDOWS || platform === PlatformType.LINUX
            ? "pt-4"
            : ""
        }`}
      >
        <AnimatePresence mode="wait">
          <motion.div
            key={window.location.pathname}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
            className="p-6 h-full"
          >
            {children}
          </motion.div>
        </AnimatePresence>

        <AnimatePresence>
          {toast && (
            <motion.div
              initial={{ opacity: 0, y: 50 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 50 }}
              transition={{ type: "spring", stiffness: 500, damping: 30 }}
            >
              <Toast
                variant={
                  toast.type === "error"
                    ? "error"
                    : toast.type === "warning"
                      ? "warning"
                      : "success"
                }
                onClose={hideToast}
              >
                <div className="font-medium">
                  {toast.type === "success"
                    ? t.toast.success
                    : toast.type === "warning"
                      ? t.toast.warning
                      : t.toast.error}
                </div>
                <div className="text-sm mt-1">{toast.message}</div>
              </Toast>
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </div>
  )
}
