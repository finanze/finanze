import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useState,
} from "react"
import enTranslations from "./locales/en.json"
import esTranslationsRaw from "./locales/es.json"
import itTranslationsRaw from "./locales/it.json"

export type Locale = "en-US" | "es-ES" | "it-IT"
export type Translations = typeof enTranslations

const translations: Record<Locale, Translations> = {
  "en-US": enTranslations,
  "es-ES": esTranslationsRaw as unknown as Translations,
  "it-IT": itTranslationsRaw as unknown as Translations,
}

const VALID_LOCALES: Locale[] = ["en-US", "es-ES", "it-IT"]

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
    if (savedLocale && VALID_LOCALES.includes(savedLocale)) {
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
