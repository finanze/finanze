import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from "react"
import { NativeModules, Platform } from "react-native"
import AsyncStorage from "@react-native-async-storage/async-storage"
import { en, Translations } from "./en"
import { es } from "./es"

type Language = "en" | "es"

interface I18nContextType {
  t: Translations
  language: Language
  setLanguage: (lang: Language) => Promise<void>
  locale: string
}

const translations: Record<Language, Translations> = {
  en,
  es,
}

const I18nContext = createContext<I18nContextType | undefined>(undefined)

const LANGUAGE_STORAGE_KEY = "finanze.language.v1"

// Get device language
function getDeviceLanguage(): Language {
  let deviceLang = "en"

  if (Platform.OS === "ios") {
    deviceLang =
      NativeModules.SettingsManager?.settings?.AppleLocale ||
      NativeModules.SettingsManager?.settings?.AppleLanguages?.[0] ||
      "en"
  } else if (Platform.OS === "android") {
    deviceLang = NativeModules.I18nManager?.localeIdentifier || "en"
  }

  // Extract language code (e.g., 'es_ES' -> 'es')
  const langCode = deviceLang.split(/[_-]/)[0].toLowerCase()

  return langCode === "es" ? "es" : "en"
}

interface I18nProviderProps {
  children: ReactNode
}

export function I18nProvider({ children }: I18nProviderProps) {
  const [language, setLanguageState] = useState<Language>("en")
  const [isLoaded, setIsLoaded] = useState(false)

  useEffect(() => {
    const loadLanguage = async () => {
      try {
        const savedLang = await AsyncStorage.getItem(LANGUAGE_STORAGE_KEY)
        if (savedLang && (savedLang === "en" || savedLang === "es")) {
          setLanguageState(savedLang)
        } else {
          setLanguageState(getDeviceLanguage())
        }
      } catch (error) {
        console.error("Failed to load language:", error)
        setLanguageState(getDeviceLanguage())
      } finally {
        setIsLoaded(true)
      }
    }

    loadLanguage()
  }, [])

  const setLanguage = useCallback(async (lang: Language) => {
    try {
      await AsyncStorage.setItem(LANGUAGE_STORAGE_KEY, lang)
      setLanguageState(lang)
    } catch (error) {
      console.error("Failed to save language:", error)
    }
  }, [])

  const locale = language === "es" ? "es-ES" : "en-US"

  if (!isLoaded) {
    return null
  }

  return (
    <I18nContext.Provider
      value={{
        t: translations[language],
        language,
        setLanguage,
        locale,
      }}
    >
      {children}
    </I18nContext.Provider>
  )
}

export function useI18n(): I18nContextType {
  const context = useContext(I18nContext)
  if (context === undefined) {
    throw new Error("useI18n must be used within an I18nProvider")
  }
  return context
}

export type { Translations, Language }
