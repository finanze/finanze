import { useState } from "react"
import { useModalBackHandler } from "@/hooks/useModalBackHandler"
import { motion, AnimatePresence } from "framer-motion"
import { createPortal } from "react-dom"
import type { Entity, EntityAccountInfo } from "@/types"
import { EntityStatus } from "@/types"
import { Badge } from "@/components/ui/Badge"
import { Button } from "@/components/ui/Button"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card"
import { ConfirmationDialog } from "@/components/ui/ConfirmationDialog"
import { useEntityWorkflow } from "@/context/EntityWorkflowContext"
import { useI18n } from "@/i18n"
import { KeyRound, RefreshCw, Unplug, X } from "lucide-react"

interface ManageAccountsDialogProps {
  entity: Entity
  isOpen: boolean
  onClose: () => void
  onAddAccount: () => void
}

export function ManageAccountsDialog({
  entity,
  isOpen,
  onClose,
  onAddAccount,
}: ManageAccountsDialogProps) {
  const { t } = useI18n()
  const { scrape, disconnectEntity, fetchingEntityState } = useEntityWorkflow()
  const [disconnectingAccountId, setDisconnectingAccountId] = useState<
    string | null
  >(null)

  useModalBackHandler(isOpen, onClose)

  const accounts = entity.accounts ?? []
  const { fetchingEntityIds } = fetchingEntityState
  const entityFetching = fetchingEntityIds.includes(entity.id)

  const handleFetch = (account: EntityAccountInfo) => {
    scrape(entity, entity.features, {}, account.id)
  }

  const handleDisconnect = async () => {
    if (!disconnectingAccountId) return
    await disconnectEntity(entity.id, disconnectingAccountId)
    setDisconnectingAccountId(null)
    onClose()
  }

  const dialogContent = (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-[18000]"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="w-full max-w-md mx-auto"
          >
            <Card className="w-full">
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>{t.entities.manageAccounts}</span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={onClose}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {accounts.length === 0 && (
                  <p className="text-sm text-muted-foreground text-center py-4">
                    {t.entities.noAccounts}
                  </p>
                )}
                {accounts.map((account, index) => (
                  <div
                    key={account.id}
                    className="flex items-center justify-between gap-2 p-3 rounded-lg border border-gray-200 dark:border-gray-700"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-sm font-medium truncate">
                        {account.name || `${t.entities.account} ${index + 1}`}
                      </span>
                      <Badge
                        variant="outline"
                        className={`text-xs flex-shrink-0 ${
                          account.status === EntityStatus.CONNECTED
                            ? "bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-300"
                            : "bg-amber-100 text-amber-800 dark:bg-amber-900/20 dark:text-amber-300"
                        }`}
                      >
                        {account.status === EntityStatus.CONNECTED
                          ? t.entities.connected
                          : t.entities.requiresLogin}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      {account.status === EntityStatus.REQUIRES_LOGIN && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-gray-600 dark:text-gray-400"
                          disabled={entityFetching}
                          title={t.entities.relogin}
                        >
                          <KeyRound className="h-4 w-4" />
                        </Button>
                      )}
                      {account.status === EntityStatus.CONNECTED && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-gray-600 dark:text-gray-400"
                          onClick={() => handleFetch(account)}
                          disabled={entityFetching}
                          title={t.entities.fetchData}
                        >
                          <RefreshCw className="h-4 w-4" />
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300"
                        onClick={() => setDisconnectingAccountId(account.id)}
                        disabled={entityFetching}
                        title={t.entities.disconnect}
                      >
                        <Unplug className="h-4 w-4" strokeWidth={2.5} />
                      </Button>
                    </div>
                  </div>
                ))}
              </CardContent>
              <CardFooter>
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={onAddAccount}
                >
                  {t.entities.addAccount}
                </Button>
              </CardFooter>
            </Card>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )

  return (
    <>
      {typeof document !== "undefined"
        ? createPortal(dialogContent, document.body)
        : dialogContent}
      <ConfirmationDialog
        isOpen={disconnectingAccountId !== null}
        title={t.entities.confirmDisconnect}
        message={t.entities.confirmDisconnectMessage.replace(
          "{entity}",
          entity.name,
        )}
        confirmText={t.entities.disconnect}
        cancelText={t.common.cancel}
        onConfirm={handleDisconnect}
        onCancel={() => setDisconnectingAccountId(null)}
      />
    </>
  )
}
