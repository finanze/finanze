import { Sun, Moon, SunMoon } from "lucide-react"
import { Button } from "@/components/ui/Button"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import { useTheme } from "@/context/ThemeContext"
import { useI18n } from "@/i18n"

export function ThemeSelector() {
  const { theme, setThemeMode } = useTheme()
  const { t } = useI18n()

  return (
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
  )
}

export { LoginQuickSettings } from "./LoginQuickSettings"
