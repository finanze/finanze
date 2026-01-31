import { useEffect, useState } from "react"
import type { ReactNode } from "react"
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
import { PlatformType } from "@/types"
import {
  getPlatformAssets,
  formatFileSize,
  formatReleaseDate,
} from "@/utils/releaseUtils"
import {
  Download,
  ExternalLink,
  Calendar,
  Package,
  ChevronDown,
  ChevronRight,
} from "lucide-react"
import { motion, AnimatePresence } from "framer-motion"
import ReactMarkdown from "react-markdown"
import { getPlatformType } from "@/lib/platform"

interface ReleaseUpdateModalProps {
  isOpen: boolean
  onClose: () => void
  currentVersion: string
  latestVersion: string
  release: GitHubRelease
  onSkipVersion?: (version: string) => void
  autoUpdateSupported: boolean
  isAutoUpdateDownloading: boolean
  autoUpdateProgress: number | null
  autoUpdateDownloadedBytes: number | null
  autoUpdateTotalBytes: number | null
  isAutoUpdateDownloaded: boolean
  autoUpdateErrorMessage: string | null
  onStartAutoUpdate?: () => void
  onInstallAutoUpdate?: () => void
}

export function ReleaseUpdateModal({
  isOpen,
  onClose,
  currentVersion,
  latestVersion,
  release,
  onSkipVersion,
  autoUpdateSupported,
  isAutoUpdateDownloading,
  autoUpdateProgress,
  autoUpdateDownloadedBytes,
  autoUpdateTotalBytes,
  isAutoUpdateDownloaded,
  autoUpdateErrorMessage,
  onStartAutoUpdate,
  onInstallAutoUpdate,
}: ReleaseUpdateModalProps) {
  const { t, locale } = useI18n()
  const [showFullNotes, setShowFullNotes] = useState(false)
  const [showManualDownloads, setShowManualDownloads] =
    useState(!autoUpdateSupported)

  if (!isOpen) return null

  const platform = getPlatformType()
  const platformAssets = getPlatformAssets(release, platform)
  const releaseDate = formatReleaseDate(release.published_at, locale)

  const getPlatformDisplayName = (
    platformType: PlatformType | null,
  ): string => {
    switch (platformType) {
      case PlatformType.MAC:
        return "macOS"
      case PlatformType.WINDOWS:
        return "Windows"
      case PlatformType.LINUX:
        return "Linux"
      case PlatformType.WEB:
        return "Web"
      default:
        return "Unknown"
    }
  }

  const handleDownload = (url: string) => {
    window.open(url, "_blank")
  }

  const handleViewRelease = () => {
    window.open(release.html_url, "_blank")
  }

  const handleSkipVersion = () => {
    if (onSkipVersion) {
      onSkipVersion(latestVersion)
    }
    onClose()
  }

  // Truncate release notes for preview
  const truncateText = (text: string, maxLength: number = 500): string => {
    if (text.length <= maxLength) return text
    return text.substring(0, maxLength) + "..."
  }

  useEffect(() => {
    setShowManualDownloads(!autoUpdateSupported)
  }, [autoUpdateSupported])

  useEffect(() => {
    if (autoUpdateSupported && autoUpdateErrorMessage) {
      setShowManualDownloads(true)
    }
  }, [autoUpdateSupported, autoUpdateErrorMessage])

  const renderAutoUpdateSection = () => {
    if (!autoUpdateSupported) {
      return null
    }

    const progressValue = Math.min(100, Math.max(0, autoUpdateProgress ?? 0))

    const progressLabel =
      autoUpdateDownloadedBytes !== null && autoUpdateTotalBytes !== null
        ? t.release.autoUpdate.progress
            .replace("{percent}", Math.round(progressValue).toString())
            .replace("{downloaded}", formatFileSize(autoUpdateDownloadedBytes))
            .replace("{total}", formatFileSize(autoUpdateTotalBytes))
        : t.release.autoUpdate.progressFallback.replace(
            "{percent}",
            Math.round(progressValue).toString(),
          )

    const handleAutoUpdateDownload = () => {
      onStartAutoUpdate?.()
    }

    const handleAutoUpdateInstall = () => {
      onInstallAutoUpdate?.()
    }

    return (
      <div className="space-y-3">
        <h4 className="font-medium text-sm">{t.release.autoUpdate.title}</h4>
        <p className="text-sm text-muted-foreground">
          {t.release.autoUpdate.description}
        </p>
        {autoUpdateErrorMessage && (
          <p className="text-xs text-destructive-foreground">
            {autoUpdateErrorMessage}
          </p>
        )}
        {isAutoUpdateDownloaded ? (
          <Button
            onClick={handleAutoUpdateInstall}
            className="w-full sm:w-auto"
            disabled={!onInstallAutoUpdate}
          >
            {t.release.autoUpdate.install}
          </Button>
        ) : (
          <Button
            onClick={handleAutoUpdateDownload}
            className="w-full sm:w-auto"
            disabled={isAutoUpdateDownloading || !onStartAutoUpdate}
          >
            {isAutoUpdateDownloading
              ? t.release.autoUpdate.downloading
              : t.release.autoUpdate.download}
          </Button>
        )}
        {isAutoUpdateDownloading && (
          <div className="space-y-2">
            <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
              <div
                className="h-full bg-green-500 transition-all"
                style={{ width: `${progressValue}%` }}
              />
            </div>
            <p className="text-xs text-muted-foreground">{progressLabel}</p>
          </div>
        )}
        {isAutoUpdateDownloaded && (
          <p className="text-xs text-muted-foreground">
            {t.release.autoUpdate.ready}
          </p>
        )}
      </div>
    )
  }

  let manualDownloadContent: ReactNode = null

  if (platformAssets.length > 0) {
    manualDownloadContent = (
      <>
        <h4 className="font-medium text-sm">
          {t.release.downloadFor.replace(
            "{platform}",
            getPlatformDisplayName(platform),
          )}
        </h4>
        <div className="space-y-2">
          {platformAssets.map((asset, index) => (
            <div
              key={index}
              className="flex flex-col sm:flex-row sm:items-center sm:justify-between p-3 bg-muted rounded-lg gap-3"
            >
              <div className="flex-1 min-w-0">
                <div className="font-medium text-sm break-all">
                  {asset.name}
                </div>
                <div className="text-xs text-muted-foreground">
                  {formatFileSize(asset.size)}
                </div>
              </div>
              <Button
                onClick={() => handleDownload(asset.url)}
                size="sm"
                className="w-full sm:w-auto flex-shrink-0"
              >
                <Download className="h-4 w-4 mr-1" />
                {t.common.download}
              </Button>
            </div>
          ))}
        </div>
      </>
    )
  } else if (platform === PlatformType.WEB) {
    manualDownloadContent = (
      <>
        <h4 className="font-medium text-sm">{t.release.downloadAssets}</h4>
        <div className="p-3 bg-muted rounded-lg">
          <p className="text-sm text-muted-foreground mb-3">
            {t.release.releasePageLink}
          </p>
          <Button
            onClick={handleViewRelease}
            size="sm"
            className="w-full sm:w-auto"
          >
            <ExternalLink className="h-4 w-4 mr-1" />
            {t.common.viewRelease}
          </Button>
        </div>
      </>
    )
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-2 sm:p-4 z-50">
      <AnimatePresence>
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.9 }}
          transition={{ duration: 0.2 }}
          className="w-full"
        >
          <Card className="w-full max-w-2xl mx-auto max-h-[95vh] sm:max-h-[90vh] flex flex-col">
            <CardHeader className="flex-shrink-0 px-4 pt-4 pb-0 sm:pt-6 sm:px-6">
              <CardTitle className="flex items-center gap-2 text-green-600 dark:text-green-400 text-lg sm:text-xl">
                <Package className="h-5 w-5 flex-shrink-0" />
                {t.release.newVersionAvailable}
              </CardTitle>
              <div className="flex flex-col gap-2 text-sm text-muted-foreground">
                <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
                  <span className="text-xs sm:text-sm">
                    {t.release.currentVersion}:{" "}
                    <code className="bg-muted px-1 rounded text-xs">
                      {currentVersion}
                    </code>
                  </span>
                  <span className="text-xs sm:text-sm">
                    {t.release.latestVersion}:{" "}
                    <code className="bg-green-100 dark:bg-green-900 px-1 rounded text-xs text-green-700 dark:text-green-300">
                      {latestVersion}
                    </code>
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <Calendar className="h-4 w-4 flex-shrink-0" />
                  <span className="text-xs sm:text-sm">
                    {t.release.publishedOn} {releaseDate}
                  </span>
                </div>
              </div>
            </CardHeader>

            <CardContent className="flex-1 overflow-y-auto min-h-0 space-y-4 p-4 sm:p-6">
              {renderAutoUpdateSection()}
              {manualDownloadContent && (
                <div className="space-y-3">
                  {autoUpdateSupported && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowManualDownloads(prev => !prev)}
                      className="w-full sm:w-auto justify-start gap-2"
                    >
                      {showManualDownloads ? (
                        <ChevronDown className="h-4 w-4" />
                      ) : (
                        <ChevronRight className="h-4 w-4" />
                      )}
                      {showManualDownloads
                        ? t.release.manualDownloads.hide
                        : t.release.manualDownloads.show}
                    </Button>
                  )}

                  {(!autoUpdateSupported || showManualDownloads) && (
                    <div className="space-y-3">{manualDownloadContent}</div>
                  )}
                </div>
              )}

              {/* Release Notes */}
              <div className="space-y-3">
                <h4 className="font-medium text-sm">{t.release.whatsNew}</h4>
                <div className="bg-muted p-3 sm:p-4 rounded-lg">
                  <div className="prose prose-sm dark:prose-invert max-w-none prose-headings:text-foreground prose-headings:font-semibold prose-h1:text-base prose-h2:text-sm prose-h3:text-sm prose-p:text-muted-foreground prose-p:leading-relaxed prose-strong:text-foreground prose-strong:font-semibold prose-ul:text-muted-foreground prose-ol:text-muted-foreground prose-li:text-muted-foreground prose-li:my-1 prose-ul:pl-4 prose-ol:pl-4 prose-li:pl-1">
                    <ReactMarkdown
                      components={{
                        h1: ({ children }) => (
                          <h1 className="text-base font-semibold text-foreground mb-2">
                            {children}
                          </h1>
                        ),
                        h2: ({ children }) => (
                          <h2 className="text-sm font-semibold text-foreground mb-2">
                            {children}
                          </h2>
                        ),
                        h3: ({ children }) => (
                          <h3 className="text-sm font-semibold text-foreground mb-1">
                            {children}
                          </h3>
                        ),
                        p: ({ children }) => (
                          <p className="text-muted-foreground leading-relaxed mb-2">
                            {children}
                          </p>
                        ),
                        ul: ({ children }) => (
                          <ul className="list-disc pl-4 text-muted-foreground space-y-1">
                            {children}
                          </ul>
                        ),
                        ol: ({ children }) => (
                          <ol className="list-decimal pl-4 text-muted-foreground space-y-1">
                            {children}
                          </ol>
                        ),
                        li: ({ children }) => (
                          <li className="text-muted-foreground">{children}</li>
                        ),
                        strong: ({ children }) => (
                          <strong className="font-semibold text-foreground">
                            {children}
                          </strong>
                        ),
                        em: ({ children }) => (
                          <em className="italic text-muted-foreground">
                            {children}
                          </em>
                        ),
                        code: ({ children }) => (
                          <code className="bg-background px-1 py-0.5 rounded text-xs font-mono text-foreground">
                            {children}
                          </code>
                        ),
                      }}
                    >
                      {showFullNotes
                        ? release.body
                        : truncateText(release.body)}
                    </ReactMarkdown>
                  </div>
                  {release.body.length > 500 && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowFullNotes(!showFullNotes)}
                      className="mt-3 text-xs"
                    >
                      {showFullNotes ? "Show Less" : "Show More"}
                    </Button>
                  )}
                </div>
              </div>
            </CardContent>

            <CardFooter className="flex-shrink-0 flex flex-col sm:flex-row sm:justify-between gap-3 p-4 sm:p-6 pt-6">
              <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
                <Button
                  variant="outline"
                  onClick={onClose}
                  className="w-full sm:w-auto"
                >
                  {t.common.remindLater}
                </Button>
                {onSkipVersion && (
                  <Button
                    variant="ghost"
                    onClick={handleSkipVersion}
                    size="sm"
                    className="w-full sm:w-auto"
                  >
                    {t.release.skipThisVersion}
                  </Button>
                )}
              </div>
              <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
                <Button
                  variant="outline"
                  onClick={handleViewRelease}
                  className="w-full sm:w-auto"
                >
                  <ExternalLink className="h-4 w-4 mr-1" />
                  {t.common.viewRelease}
                </Button>
                <Button onClick={onClose} className="w-full sm:w-auto">
                  {t.common.close}
                </Button>
              </div>
            </CardFooter>
          </Card>
        </motion.div>
      </AnimatePresence>
    </div>
  )
}
