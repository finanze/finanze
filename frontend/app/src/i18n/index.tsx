import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useState,
} from "react"
import enTranslations from "./locales/en.json"
import esTranslations from "./locales/es.json"

export type Locale = "en-US" | "es-ES"
export type Translations =
  | (typeof enTranslations & { about: (typeof enTranslations)["about"] })
  | (typeof esTranslations & { about: (typeof enTranslations)["about"] })

const translations: Record<Locale, Translations> = {
  "en-US": enTranslations,
  "es-ES": esTranslations,
}

interface I18nContextType {
  locale: Locale
  t: Translations
  changeLocale: (newLocale: Locale) => void
}

const I18nContext = createContext<I18nContextType | undefined>(undefined)

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocale] = useState<Locale>("en-US")
  const [t, setT] = useState<Translations>(translations[locale])

  const changeLocale = (newLocale: Locale) => {
    setLocale(newLocale)
    setT(translations[newLocale])
    localStorage.setItem("locale", newLocale)
  }

  useEffect(() => {
    const savedLocale = localStorage.getItem("locale") as Locale
    if (savedLocale && (savedLocale === "en-US" || savedLocale === "es-ES")) {
      setLocale(savedLocale)
      setT(translations[savedLocale])
    }
  }, [])

  return (
    <I18nContext.Provider value={{ locale, t, changeLocale }}>
      {children}
    </I18nContext.Provider>
  )
}

export function useI18n() {
  const context = useContext(I18nContext)
  if (context === undefined) {
    throw new Error("useI18n must be used within an I18nProvider")
  }
  return context
}
