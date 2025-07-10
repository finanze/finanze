import { useState } from "react"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { FileSpreadsheet, FileUp, Check, PackageSearch } from "lucide-react"
import { motion } from "framer-motion"
import { Badge } from "@/components/ui/Badge"
import { cn } from "@/lib/utils"
import { updateSheets } from "@/services/api"
import { ExportTarget } from "@/types"

export default function ExportPage() {
  const { t } = useI18n()
  const { settings, exportState, setExportState, showToast } = useAppContext()
  const [successAnimation, setSuccessAnimation] = useState(false)

  const handleExport = async () => {
    try {
      setExportState(prev => ({ ...prev, isExporting: true }))
      await updateSheets({ target: ExportTarget.GOOGLE_SHEETS })

      // Show success animation
      setSuccessAnimation(true)
      showToast(t.common.exportSuccess, "success")
      setExportState(prev => ({
        ...prev,
        isExporting: false,
        lastExportTime: Date.now(),
      }))

      setTimeout(() => {
        setSuccessAnimation(false)
      }, 2000)
    } catch (error) {
      console.error("Export error:", error)
      showToast(t.common.exportError, "error")
      setExportState(prev => ({ ...prev, isExporting: false }))
    }
  }

  const sheetsConfig = settings?.export?.sheets
  const sheetsEnabled = sheetsConfig?.enabled || false
  const sheetId = sheetsConfig?.globals?.spreadsheetId || ""

  // Count how many sections are configured
  const sectionCounts = {
    position: sheetsConfig?.position?.length || 0,
    contributions: sheetsConfig?.contributions?.length || 0,
    transactions: sheetsConfig?.transactions?.length || 0,
    historic: sheetsConfig?.historic?.length || 0,
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">{t.export.title}</h1>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center">
                  <FileSpreadsheet className="mr-2 h-5 w-5 text-green-600" />
                  <CardTitle>Google Sheets</CardTitle>
                </div>
                <Badge
                  className={cn(
                    sheetsEnabled
                      ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
                      : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
                  )}
                >
                  {sheetsEnabled ? t.common.enabled : t.common.disabled}
                </Badge>
              </div>
              <CardDescription>{t.export.description}</CardDescription>
            </CardHeader>
            {sheetsEnabled ? (
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 gap-3">
                  <div className="rounded-lg border p-3">
                    <div className="text-sm font-medium mb-2">
                      {t.export.spreadsheetId}
                    </div>
                    <div className="text-xs text-muted-foreground font-mono bg-gray-100 dark:bg-gray-900 p-2 rounded">
                      {sheetId}
                    </div>
                  </div>

                  <div className="rounded-lg border p-3">
                    <div className="text-sm font-medium mb-2">
                      {t.export.configuredSections}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(sectionCounts).map(([section, count]) =>
                        count > 0 ? (
                          <Badge
                            key={section}
                            variant="secondary"
                            className="capitalize"
                          >
                            {t.settings[section as keyof typeof t.settings] ||
                              section}{" "}
                            ({count})
                          </Badge>
                        ) : null,
                      )}
                    </div>
                  </div>
                </div>

                <div className="pt-2">
                  <Button
                    onClick={handleExport}
                    disabled={exportState.isExporting || successAnimation}
                    className="w-full relative"
                  >
                    {exportState.isExporting && (
                      <LoadingSpinner className="h-5 w-5 mr-2" />
                    )}
                    {successAnimation ? (
                      <motion.div
                        initial={{ scale: 0.5, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        className="flex items-center"
                      >
                        <Check className="mr-2 h-4 w-4" />
                        {t.common.exportSuccess}
                      </motion.div>
                    ) : (
                      <>
                        <FileUp className="mr-2 h-4 w-4" />
                        {t.common.export}
                      </>
                    )}
                  </Button>
                </div>
              </CardContent>
            ) : (
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  {t.export.disabledMessage}
                </p>
              </CardContent>
            )}
          </Card>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <Card className="h-full border-dashed">
            <CardHeader className="flex flex-col items-center justify-center text-center h-full">
              <PackageSearch className="h-12 w-12 text-muted-foreground mb-4" />
              <CardTitle>{t.common.comingSoon}</CardTitle>
              <CardDescription>{t.export.moreOptionsNote}</CardDescription>
            </CardHeader>
          </Card>
        </motion.div>
      </div>
    </div>
  )
}
