import type React from "react"
import { useRef } from "react"
import { Sidebar } from "./Sidebar"
import { Toast } from "@/components/ui/Toast"
import { useAppContext } from "@/context/AppContext"
import { motion, AnimatePresence } from "framer-motion"
import { PlatformType } from "@/types"
import { useI18n } from "@/i18n"
import { useLocation } from "react-router-dom"
import { getPlatformType } from "@/lib/platform"

interface LayoutProps {
  children: React.ReactNode
}

export function Layout({ children }: LayoutProps) {
  const { toast, hideToast } = useAppContext()
  const { t } = useI18n()
  const location = useLocation()
  const prevPathnameRef = useRef(location.pathname)
  const platform = getPlatformType()
  const isRouteChange = prevPathnameRef.current !== location.pathname
  if (isRouteChange) {
    prevPathnameRef.current = location.pathname
  }

  return (
    <>
      <div className="flex h-screen min-h-0 overflow-hidden bg-gray-50 dark:bg-black text-gray-900 dark:text-gray-100">
        <Sidebar />
        <main
          className={`flex-1 min-h-0 overflow-auto ${
            platform === PlatformType.WINDOWS || platform === PlatformType.LINUX
              ? "pt-4"
              : ""
          }`}
        >
          <motion.div
            key={location.pathname}
            initial={isRouteChange ? { opacity: 0, y: 10 } : false}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
            className="p-6 h-full"
          >
            {children}
          </motion.div>
        </main>
      </div>

      <AnimatePresence>
        {toast && (
          <Toast
            isAnimating
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
        )}
      </AnimatePresence>
    </>
  )
}
