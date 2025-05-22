import type React from "react"

import { Sidebar } from "./Sidebar"
import { Toast } from "@/components/ui/Toast"
import { useAppContext } from "@/context/AppContext"
import { motion, AnimatePresence } from "framer-motion"

interface LayoutProps {
  children: React.ReactNode
}

export function Layout({ children }: LayoutProps) {
  const { toast, hideToast } = useAppContext()

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-black text-gray-900 dark:text-gray-100">
      <Sidebar />
      <main className="flex-1 overflow-auto">
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
                variant={toast.type === "error" ? "destructive" : toast.type === "warning" ? "warning" : "default"}
                onClose={hideToast}
                className={
                  toast.type === "success"
                    ? "bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800"
                    : undefined
                }
              >
                <div className="font-medium">
                  {toast.type === "success" ? "Success" : toast.type === "warning" ? "Warning" : "Error"}
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
