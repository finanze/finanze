import { describe, expect, it } from "vitest"
import en from "@/i18n/locales/en.json"
import es from "@/i18n/locales/es.json"
import itTranslations from "@/i18n/locales/it.json"
import {
  getIntegrationFamilyName,
  getIntegrationMethodName,
  getIntegrationName,
} from "@/lib/integrations"

describe("integration display names", () => {
  it.each([
    [en, ["Custom AI", "Local models", "Claude Agent"]],
    [es, ["IA personalizada", "Modelos locales", "Agente de Claude"]],
    [
      itTranslations,
      ["IA personalizzata", "Modelli locali", "Agente di Claude"],
    ],
  ] as const)(
    "resolves each locale's descriptive names without metadata",
    (translations, names) => {
      const ids = ["OPENAI_COMPATIBLE", "LOCAL_MODELS", "CLAUDE_AGENT"]
      ids.forEach((id, index) => {
        expect(getIntegrationName(translations, id)).toBe(names[index])
        expect(
          getIntegrationName(translations, id, { id, name: "My provider" }),
        ).toBe(names[index])
      })
      expect(getIntegrationName(translations, "GOOGLE_SHEETS")).toBe(
        "Google Sheets",
      )
      expect(getIntegrationName(translations, "ENABLE_BANKING")).toBe(
        "Enable Banking",
      )
      expect(
        Object.entries(translations.settings.integration)
          .filter(([, copy]) => "name" in copy)
          .map(([id]) => id)
          .sort(),
      ).toEqual([
        "CLAUDE_AGENT",
        "ENABLE_BANKING",
        "GOOGLE_SHEETS",
        "LOCAL_MODELS",
        "OPENAI_COMPATIBLE",
      ])
    },
  )

  it.each([en, es, itTranslations])(
    "uses backend brand names without requiring translation entries",
    translations => {
      const integration = Object.freeze({ id: "OPENAI", name: "OpenAI" })
      expect(
        getIntegrationName(translations, integration.id, integration),
      ).toBe("OpenAI")
      expect(integration).toEqual({ id: "OPENAI", name: "OpenAI" })
    },
  )

  it("prefers optional translated names over backend names", () => {
    const translations = {
      ...en,
      settings: {
        ...en.settings,
        integration: {
          ...en.settings.integration,
          LOCAL_MODELS: {
            ...en.settings.integration.LOCAL_MODELS,
            name: "Translated models",
          },
        },
      },
    }
    expect(
      getIntegrationName(translations, "LOCAL_MODELS", {
        id: "LOCAL_MODELS",
        name: "Manually edited name",
      }),
    ).toBe("Translated models")
    expect(getIntegrationName(translations, "LOCAL_MODELS")).toBe(
      "Translated models",
    )
  })

  it("supports unknown integration IDs and missing or empty metadata", () => {
    expect(
      getIntegrationName(en, "FUTURE_API", {
        id: "FUTURE_API",
        name: "Future API",
      }),
    ).toBe("Future API")
    expect(getIntegrationName(en, "FUTURE_API")).toBe("FUTURE_API")
    expect(
      getIntegrationName(en, "FUTURE_API", { id: "FUTURE_API", name: " " }),
    ).toBe("FUTURE_API")
  })

  it("keeps localized family and method labels distinct", () => {
    expect(
      getIntegrationFamilyName(es, {
        id: "LOCAL_MODELS",
        name: "Local models",
      }),
    ).toBe("Modelos locales")
    expect(getIntegrationMethodName(es, "LOCAL_MODELS")).toBe(
      "Entorno local o servidor",
    )
    expect(getIntegrationMethodName(itTranslations, "CHATGPT")).toBe(
      "Piano ChatGPT",
    )
  })

  it("supports unknown families and methods without a frontend registry", () => {
    expect(
      getIntegrationFamilyName(en, {
        id: "FUTURE_FAMILY",
        name: "Future Service",
      }),
    ).toBe("Future Service")
    expect(
      getIntegrationFamilyName(en, { id: "FUTURE_FAMILY", name: "" }),
    ).toBe("FUTURE_FAMILY")
    expect(
      getIntegrationMethodName(en, "FUTURE_API", {
        id: "FUTURE_API",
        name: "Future API",
      }),
    ).toBe("Future API")
    expect(getIntegrationMethodName(en, "FUTURE_API")).toBe("FUTURE_API")
  })
})
