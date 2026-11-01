import { motion } from "framer-motion"
import { useI18n } from "@/i18n"
import { useTheme } from "@/context/ThemeContext"
import { isLightTheme } from "@/components/auth/authStyles"

export function RestrictedRegionScreen() {
  const { t } = useI18n()
  const { theme } = useTheme()
  const isLight = isLightTheme(theme)

  return (
    <div
      data-testid="region-restricted-screen"
      className={`min-h-screen flex items-center justify-center p-4 select-none ${
        isLight ? "bg-white" : "bg-black"
      }`}
    >
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-sm flex flex-col items-center px-10"
      >
        <img
          src="finanze-fg.svg"
          alt="Finanze Logo"
          className={`select-none pointer-events-none mb-5 ${isLight ? "invert" : ""}`}
          style={{ width: 56, height: 56 }}
          draggable={false}
        />
        <h1
          className={`text-xl font-medium text-center mb-4 tracking-tight ${isLight ? "text-black" : "text-white"}`}
        >
          {t.login.regionRestricted.title}
        </h1>
        <p
          className={`text-center text-sm ${isLight ? "text-black/60" : "text-white/60"}`}
        >
          {t.login.regionRestricted.description}
        </p>
      </motion.div>
    </div>
  )
}
