import React from "react"
import { createRoot } from "react-dom/client"
import { HashRouter } from "react-router-dom"
import App from "./App"
import "./index.css"
import { AppProvider } from "@/context/AppContext"
import { I18nProvider } from "@/i18n"
import { ThemeProvider } from "@/context/ThemeContext"
import { AuthProvider } from "@/context/AuthContext"

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <HashRouter>
      <ThemeProvider>
        <I18nProvider>
          <AuthProvider>
            <AppProvider>
              <App />
            </AppProvider>
          </AuthProvider>
        </I18nProvider>
      </ThemeProvider>
    </HashRouter>
  </React.StrictMode>,
)
