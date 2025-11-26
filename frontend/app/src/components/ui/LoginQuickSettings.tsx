import { useState, useEffect } from "react"
import { Sun, Moon, SunMoon, Globe, Wrench } from "lucide-react"
import { Button } from "@/components/ui/Button"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import { useTheme } from "@/context/ThemeContext"
import { useI18n } from "@/i18n"
import type { Locale } from "@/i18n"

interface LoginQuickSettingsProps {
  isDesktop?: boolean
  onOpenAdvancedSettings?: () => void
}

export function LoginQuickSettings({
  isDesktop,
  onOpenAdvancedSettings,
}: LoginQuickSettingsProps) {
  const { theme, setThemeMode } = useTheme()
  const { t, locale, changeLocale } = useI18n()
  const [detectedDesktop, setDetectedDesktop] = useState<boolean>(
    Boolean(isDesktop),
  )

  useEffect(() => {
    if (typeof isDesktop === "boolean") {
      setDetectedDesktop(isDesktop)
      return
    }

    if (typeof window !== "undefined" && window.ipcAPI) {
      setDetectedDesktop(true)
    }
  }, [isDesktop])

  const languages: { code: Locale; label: string }[] = [
    { code: "en-US", label: "EN" },
    { code: "es-ES", label: "ES" },
  ]

  return (
    <div className="flex gap-2">
      {/* Language Selector */}
      <Popover>
        <PopoverTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="rounded-full h-10 w-10 hover:bg-gray-200 dark:hover:bg-gray-800"
          >
            <Globe size={18} />
          </Button>
        </PopoverTrigger>
        <PopoverContent side="top" className="p-2 w-auto">
          <div className="flex flex-col gap-1">
            {languages.map(lang => (
              <Button
                key={lang.code}
                variant={locale === lang.code ? "default" : "outline"}
                size="sm"
                onClick={() => changeLocale(lang.code)}
              >
                {lang.label}
              </Button>
            ))}
          </div>
        </PopoverContent>
      </Popover>

      {/* Theme Selector */}
      <Popover>
        <PopoverTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="rounded-full h-10 w-10 hover:bg-gray-200 dark:hover:bg-gray-800"
          >
            {theme === "light" && <Sun size={18} />}
            {theme === "dark" && <Moon size={18} />}
            {theme === "system" && <SunMoon size={18} />}
          </Button>
        </PopoverTrigger>
        <PopoverContent side="top" className="p-2 w-auto">
          <div className="flex flex-col gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setThemeMode("light")}
              disabled={theme === "light"}
              className="justify-start"
            >
              <Sun size={16} className="mr-2" />
              {t.common.light}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setThemeMode("dark")}
              disabled={theme === "dark"}
              className="justify-start"
            >
              <Moon size={16} className="mr-2" />
              {t.common.dark}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setThemeMode("system")}
              disabled={theme === "system"}
              className="justify-start"
            >
              <SunMoon size={16} className="mr-2" />
              {t.common.system}
            </Button>
          </div>
        </PopoverContent>
      </Popover>

      {/* Advanced Settings (Desktop only) */}
      {detectedDesktop && onOpenAdvancedSettings && (
        <Button
          variant="ghost"
          size="icon"
          className="rounded-full h-10 w-10 hover:bg-gray-200 dark:hover:bg-gray-800"
          onClick={onOpenAdvancedSettings}
        >
          <Wrench size={18} />
        </Button>
      )}
    </div>
  )
}
