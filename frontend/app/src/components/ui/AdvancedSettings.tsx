import { X } from "lucide-react"
import { AnimatePresence, motion } from "framer-motion"
import { Button } from "@/components/ui/Button"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card"
import { useI18n } from "@/i18n"
import { AdvancedSettingsForm } from "@/components/ui/AdvancedSettingsForm"

interface AdvancedSettingsProps {
  isOpen: boolean
  onClose: () => void
}

export function AdvancedSettings({ isOpen, onClose }: AdvancedSettingsProps) {
  const { t } = useI18n()

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          key="advanced-settings"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <motion.div
            className="w-full max-w-lg max-h-[90vh]"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
          >
            <Card className="w-full h-full max-h-[90vh] shadow-xl flex flex-col overflow-hidden">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-xl font-bold">
                  {t.advancedSettings.title}
                </CardTitle>
                <Button variant="ghost" size="icon" onClick={onClose}>
                  <X className="h-4 w-4" />
                </Button>
              </CardHeader>
              <CardContent className="py-4 flex-1 overflow-y-auto min-h-0">
                <AdvancedSettingsForm
                  idPrefix="modal"
                  onSaveComplete={onClose}
                />
              </CardContent>
            </Card>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
