import React from "react"
import { createRoot } from "react-dom/client"
import { HashRouter } from "react-router-dom"
import App from "./App"
import "./index.css"
import { AppProvider } from "@/context/AppContext"
import { I18nProvider } from "@/i18n"
import { ThemeProvider } from "@/context/ThemeContext"
import { AuthProvider } from "@/context/AuthContext"
import { CloudProvider } from "@/context/CloudContext"
import { initDevPlatformOverride } from "@/lib/dev/initDevPlatformOverride"
import * as mobile from "@/lib/mobile"

async function bootstrap(): Promise<void> {
  await mobile.preinit()

  initDevPlatformOverride()
  mobile.init()

  createRoot(document.getElementById("root")!).render(
    <HashRouter>
      <ThemeProvider>
        <I18nProvider>
          <AuthProvider>
            <AppProvider>
              <CloudProvider>
                <App />
              </CloudProvider>
            </AppProvider>
          </AuthProvider>
        </I18nProvider>
      </ThemeProvider>
    </HashRouter>,
  )
}

bootstrap()
