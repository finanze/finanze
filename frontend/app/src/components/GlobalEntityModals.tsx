import { motion, AnimatePresence } from "framer-motion"
import { useLocation } from "react-router-dom"
import { useEntityWorkflow } from "@/context/EntityWorkflowContext"
import { useI18n } from "@/i18n"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { PinPad } from "@/components/PinPad"
import { ExternalLink } from "lucide-react"

export function GlobalEntityModals() {
  const { selectedEntity, pinRequired, view, isLoggingIn } = useEntityWorkflow()
  const { t } = useI18n()
  const location = useLocation()

  const isOnEntitiesPage = location.pathname === "/entities"

  return (
    <>
      {/* Global External Login Modal - shown when not on entities page */}
      <AnimatePresence>
        {view === "external-login" && selectedEntity && !isOnEntitiesPage && (
          <motion.div
            key="global-external-login-modal"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 px-4 py-8"
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="relative w-full max-w-md mx-auto"
            >
              <Card className="w-full">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <ExternalLink className="h-5 w-5" />
                    {t.login.externalLogin} {selectedEntity.name}
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col items-center py-8">
                  <LoadingSpinner size="lg" />
                  <p className="mt-4 text-center text-muted-foreground">
                    {t.login.externalLoginInProgress}
                  </p>
                </CardContent>
              </Card>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Global PIN Modal - shown when not on entities page */}
      <AnimatePresence>
        {pinRequired && selectedEntity && !isOnEntitiesPage && (
          <motion.div
            key="global-pin-modal"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 px-4 py-8"
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="relative w-full max-w-md mx-auto"
            >
              {isLoggingIn ? (
                <Card className="w-full">
                  <CardContent className="flex flex-col items-center py-8">
                    <LoadingSpinner size="lg" />
                    <p className="mt-4 text-center text-muted-foreground">
                      {t.common.loading}
                    </p>
                  </CardContent>
                </Card>
              ) : (
                <PinPad />
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
