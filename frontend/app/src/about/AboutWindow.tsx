import { useEffect, useMemo, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { useI18n } from "@/i18n"
import type { AboutAppInfo } from "@/types"

export function AboutWindow() {
  const { t } = useI18n()
  const [info, setInfo] = useState<AboutAppInfo | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const aboutStrings = t.about

  useEffect(() => {
    let mounted = true

    const loadInfo = async () => {
      try {
        const aboutInfo = await window.ipcAPI?.getAboutInfo?.()
        if (mounted) {
          setInfo(aboutInfo ?? null)
        }
      } catch (error) {
        console.error("Failed to load about info", error)
      } finally {
        if (mounted) {
          setIsLoading(false)
        }
      }
    }

    void loadInfo()

    return () => {
      mounted = false
    }
  }, [])

  useEffect(() => {
    const appName = info?.appName
    document.title = aboutStrings.title.replace("{appName}", appName!)
  }, [info?.appName, aboutStrings.title])

  const author = useMemo(() => {
    if (!info) return aboutStrings.unknownAuthor
    return info.author ?? aboutStrings.unknownAuthor
  }, [info, aboutStrings.unknownAuthor])

  const runtimeItems = useMemo(() => {
    if (!info) return []

    const items: { label: string; value: string }[] = [
      { label: aboutStrings.version, value: info.version },
    ]

    if (info.electronVersion) {
      items.push({
        label: aboutStrings.electronVersion,
        value: info.electronVersion,
      })
    }

    if (info.chromiumVersion) {
      items.push({
        label: aboutStrings.chromiumVersion,
        value: info.chromiumVersion,
      })
    }

    if (info.nodeVersion) {
      items.push({ label: aboutStrings.nodeVersion, value: info.nodeVersion })
    }

    return items
  }, [info, author, aboutStrings])

  const platformItems = useMemo(() => {
    if (!info?.platform) return []

    const { platform } = info
    const platformNames = aboutStrings.platformNames
    const osName =
      platformNames?.[platform.type as keyof typeof platformNames] ??
      platform.type

    return [
      {
        label: aboutStrings.operatingSystem,
        value: osName,
      },
      {
        label: aboutStrings.architecture,
        value: platform.arch ?? t.common.notAvailable,
      },
      {
        label: aboutStrings.osVersion,
        value: platform.osVersion ?? t.common.notAvailable,
      },
    ]
  }, [info, aboutStrings, t.common.notAvailable])

  const linkItems = useMemo(() => {
    if (!info) return []

    const items: { label: string; value: string }[] = []

    if (info.homepage) {
      items.push({ label: aboutStrings.website, value: info.homepage })
    }

    if (info.repository) {
      items.push({ label: aboutStrings.repository, value: info.repository })
    }

    return items
  }, [info, aboutStrings.website, aboutStrings.repository])

  const handleNavigate = (url: string) => {
    window.open(url, "_blank")
  }

  const appName = info?.appName ?? "Finanze"

  return (
    <div className="min-h-screen bg-background text-foreground flex items-center justify-center p-6">
      <Card className="w-full max-w-md shadow-lg">
        <CardHeader className="flex flex-col items-center text-center space-y-3">
          <img
            src="/finanze.png"
            alt={aboutStrings.logoAlt.replace("{appName}", appName)}
            className="h-12 w-12 rounded-lg shadow-sm object-cover"
          />
          <div className="space-y-1">
            <CardTitle className="text-lg">
              {aboutStrings.title.replace("{appName}", appName)}
            </CardTitle>
            <p className="text-sm text-muted-foreground">
              {aboutStrings.projectDescription.replace("{appName}", appName)}
            </p>
            <p
              className="text-xs text-muted-foreground"
              dangerouslySetInnerHTML={{
                __html: aboutStrings.maintainedBy.replace(
                  "{author}",
                  `<span class='text-foreground font-semibold'>${author}</span>`,
                ),
              }}
            />
          </div>
        </CardHeader>

        <CardContent className="space-y-4">
          {isLoading ? (
            <div className="text-sm text-muted-foreground">
              {t.common.loading}
            </div>
          ) : info ? (
            <div className="space-y-4 text-sm overflow-y-auto max-h-[320px] pr-1">
              <section className="space-y-2">
                <h3 className="text-sm font-semibold text-foreground">
                  {aboutStrings.runtimeSection}
                </h3>
                <div className="space-y-2">
                  {runtimeItems.map(item => (
                    <div
                      key={item.label}
                      className="flex items-center justify-between"
                    >
                      <span className="text-muted-foreground">
                        {item.label}
                      </span>
                      <span className="font-medium text-foreground">
                        {item.value}
                      </span>
                    </div>
                  ))}
                </div>
              </section>

              {platformItems.length > 0 && (
                <section className="space-y-2">
                  <h3 className="text-sm font-semibold text-foreground">
                    {aboutStrings.platformSection}
                  </h3>
                  <div className="space-y-2">
                    {platformItems.map(item => (
                      <div
                        key={item.label}
                        className="flex items-center justify-between"
                      >
                        <span className="text-muted-foreground">
                          {item.label}
                        </span>
                        <span className="font-medium text-foreground">
                          {item.value}
                        </span>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {linkItems.length > 0 && (
                <section className="space-y-2">
                  <h3 className="text-sm font-semibold text-foreground">
                    {aboutStrings.linksSection}
                  </h3>
                  <div className="space-y-2">
                    {linkItems.map(link => (
                      <div key={link.label} className="flex flex-col">
                        <span className="text-muted-foreground">
                          {link.label}
                        </span>
                        <button
                          type="button"
                          onClick={() => handleNavigate(link.value)}
                          className="text-left font-medium text-primary hover:underline break-all"
                        >
                          {link.value}
                        </button>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </div>
          ) : (
            <div className="text-sm text-destructive">
              {t.common.unexpectedError}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
