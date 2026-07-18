import { useState } from "react"
import { Button } from "@/components/ui/Button"
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter,
} from "@/components/ui/Card"
import { useI18n } from "@/i18n"
import { GitHubRelease } from "@/types/release"
import {
  cleanReleaseNotes,
  formatFileSize,
  formatReleaseDate,
} from "@/utils/releaseUtils"
import { Calendar, Download, Package } from "lucide-react"
import { motion, AnimatePresence } from "framer-motion"
import { ReleaseNotes } from "@/components/ReleaseNotes"

interface MobileReleaseUpdateModalProps {
  isOpen: boolean
  onClose: () => void
  currentVersion: string
  latestVersion: string
  release: GitHubRelease
  onSkipVersion?: (version: string) => void
  isDownloading: boolean
  isDownloaded: boolean
  needsPermission: boolean
  progress: number | null
  downloadedBytes: number | null
  totalBytes: number | null
  errorMessage: string | null
  onDownload: () => void
  onInstall: () => void
}

export function MobileReleaseUpdateModal({
  isOpen,
  onClose,
  currentVersion,
  latestVersion,
  release,
  onSkipVersion,
  isDownloading,
  isDownloaded,
  needsPermission,
  progress,
  downloadedBytes,
  totalBytes,
  errorMessage,
  onDownload,
  onInstall,
}: MobileReleaseUpdateModalProps) {
  const { t, locale } = useI18n()
  const [showFullNotes, setShowFullNotes] = useState(false)

  if (!isOpen) return null

  const releaseDate = formatReleaseDate(release.published_at, locale)
  const notes = cleanReleaseNotes(release.body)

  const truncateText = (text: string, maxLength: number = 500): string => {
    if (text.length <= maxLength) return text
    return text.substring(0, maxLength) + "..."
  }

  const handleSkipVersion = () => {
    onSkipVersion?.(latestVersion)
    onClose()
  }

  const progressValue = Math.min(100, Math.max(0, progress ?? 0))

  const progressLabel =
    downloadedBytes !== null && totalBytes !== null
      ? t.release.autoUpdate.progress
          .replace("{percent}", Math.round(progressValue).toString())
          .replace("{downloaded}", formatFileSize(downloadedBytes))
          .replace("{total}", formatFileSize(totalBytes))
      : t.release.autoUpdate.progressFallback.replace(
          "{percent}",
          Math.round(progressValue).toString(),
        )

  const renderPrimaryAction = () => {
    if (isDownloaded) {
      return (
        <Button onClick={onInstall} className="w-full">
          {t.release.mobileUpdate.install}
        </Button>
      )
    }

    if (errorMessage) {
      return (
        <Button onClick={onDownload} className="w-full">
          {t.release.mobileUpdate.retry}
        </Button>
      )
    }

    return (
      <Button onClick={onDownload} className="w-full" disabled={isDownloading}>
        <Download className="h-4 w-4 mr-1" />
        {isDownloading
          ? t.release.mobileUpdate.downloading
          : t.release.mobileUpdate.download}
      </Button>
    )
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-2 sm:p-4 z-[1000000]">
      <AnimatePresence>
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.9 }}
          transition={{ duration: 0.2 }}
          className="w-full"
        >
          <Card className="w-full max-w-md mx-auto max-h-[90vh] flex flex-col">
            <CardHeader className="flex-shrink-0 px-4 pt-4 pb-0">
              <CardTitle className="flex items-center gap-2 text-green-600 dark:text-green-400 text-lg">
                <Package className="h-5 w-5 flex-shrink-0" />
                {t.release.newVersionAvailable}
              </CardTitle>
              <div className="flex flex-col gap-1 text-sm text-muted-foreground">
                <div className="flex items-center gap-2">
                  <span className="text-xs">
                    {t.release.currentVersion}:{" "}
                    <code className="bg-muted px-1 rounded text-xs">
                      {currentVersion}
                    </code>
                  </span>
                  <span className="text-xs">
                    {t.release.latestVersion}:{" "}
                    <code className="bg-green-100 dark:bg-green-900 px-1 rounded text-xs text-green-700 dark:text-green-300">
                      {latestVersion}
                    </code>
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <Calendar className="h-4 w-4 flex-shrink-0" />
                  <span className="text-xs">
                    {t.release.publishedOn} {releaseDate}
                  </span>
                </div>
              </div>
            </CardHeader>

            <CardContent className="flex-1 overflow-y-auto min-h-0 space-y-4 p-4">
              <p className="text-sm text-muted-foreground">
                {t.release.mobileUpdate.description}
              </p>

              {errorMessage && (
                <p className="text-xs text-destructive-foreground">
                  {errorMessage}
                </p>
              )}

              {needsPermission && (
                <p className="text-xs text-muted-foreground">
                  {t.release.mobileUpdate.permissionRequired}
                </p>
              )}

              {renderPrimaryAction()}

              {isDownloading && (
                <div className="space-y-2">
                  <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full bg-green-500 transition-all"
                      style={{ width: `${progressValue}%` }}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {progressLabel}
                  </p>
                </div>
              )}

              <div className="space-y-2">
                <h4 className="font-medium text-sm">{t.release.whatsNew}</h4>
                <div className="bg-muted p-3 rounded-lg">
                  <ReleaseNotes
                    content={showFullNotes ? notes : truncateText(notes)}
                  />
                  {notes.length > 500 && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowFullNotes(!showFullNotes)}
                      className="mt-2 text-xs"
                    >
                      {showFullNotes
                        ? t.release.mobileUpdate.showLess
                        : t.release.mobileUpdate.showMore}
                    </Button>
                  )}
                </div>
              </div>
            </CardContent>

            <CardFooter className="flex-shrink-0 flex gap-2 p-4 pt-4">
              <Button variant="outline" onClick={onClose} className="flex-1">
                {t.common.remindLater}
              </Button>
              {onSkipVersion && (
                <Button
                  variant="ghost"
                  onClick={handleSkipVersion}
                  size="sm"
                  className="flex-1"
                >
                  {t.release.skipThisVersion}
                </Button>
              )}
            </CardFooter>
          </Card>
        </motion.div>
      </AnimatePresence>
    </div>
  )
}
