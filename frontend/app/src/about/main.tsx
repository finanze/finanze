import React from "react"
import { createRoot } from "react-dom/client"
import "@/index.css"
import { I18nProvider } from "@/i18n"
import { ThemeProvider } from "@/context/ThemeContext"
import { AboutWindow } from "./AboutWindow"

const container = document.getElementById("root")

if (!container) {
  throw new Error("About window root element not found")
}

createRoot(container).render(
  <React.StrictMode>
    <ThemeProvider>
      <I18nProvider>
        <AboutWindow />
      </I18nProvider>
    </ThemeProvider>
  </React.StrictMode>,
)
