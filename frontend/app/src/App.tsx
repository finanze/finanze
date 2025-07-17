import { Routes, Route, Navigate } from "react-router-dom"
import { Layout } from "@/components/layout/Layout"
import EntityIntegrationsPage from "./pages/EntityIntegrationsPage"
import DashboardPage from "./pages/DashboardPage"
import SettingsPage from "./pages/SettingsPage"
import ExportPage from "./pages/ExportPage"
import TransactionsPage from "./pages/TransactionsPage"
import StocksInvestmentPage from "./pages/StocksInvestmentPage"
import FundsInvestmentPage from "./pages/FundsInvestmentPage"
import DepositsInvestmentPage from "./pages/DepositsInvestmentPage"
import FactoringInvestmentPage from "./pages/FactoringInvestmentPage"
import RealEstateCFInvestmentPage from "./pages/RealEstateCFInvestmentPage"
import CryptoInvestmentPage from "./pages/CryptoInvestmentPage"
import InvestmentsPage from "./pages/InvestmentsPage"
import LoginPage from "./pages/LoginPage"
import { useAuth } from "./context/AuthContext"
import SplashScreen from "./components/SplashScreen"
import { FinancialDataProvider } from "./context/FinancialDataContext"
import { ReleaseUpdateModal } from "./components/ReleaseUpdateModal"
import { useReleaseUpdate } from "./hooks/useReleaseUpdate"
import { useAppContext } from "./context/AppContext"
import { useState, useEffect } from "react"

function App() {
  const { isAuthenticated, isInitializing } = useAuth()
  const { platform } = useAppContext()
  const [showReleaseModal, setShowReleaseModal] = useState(false)
  const [skippedVersions, setSkippedVersions] = useState<string[]>([])

  // Load skipped versions from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem("finanze-skipped-versions")
      if (stored) {
        setSkippedVersions(JSON.parse(stored))
      }
    } catch (error) {
      console.error("Error loading skipped versions:", error)
    }
  }, [])

  // Save skipped versions to localStorage whenever they change
  useEffect(() => {
    try {
      localStorage.setItem(
        "finanze-skipped-versions",
        JSON.stringify(skippedVersions),
      )
    } catch (error) {
      console.error("Error saving skipped versions:", error)
    }
  }, [skippedVersions])

  const { updateInfo } = useReleaseUpdate({
    checkOnMount: isAuthenticated && !isInitializing,
    skipVersions: skippedVersions,
    onUpdateAvailable: () => {
      // Only show modal if user is authenticated and not already shown
      if (isAuthenticated && !showReleaseModal) {
        setShowReleaseModal(true)
      }
    },
  })

  const handleCloseReleaseModal = () => {
    setShowReleaseModal(false)
  }

  const handleSkipVersion = (version: string) => {
    setSkippedVersions(prev => [...prev, version])
    setShowReleaseModal(false)
  }

  if (isInitializing) {
    return <SplashScreen />
  }

  if (!isAuthenticated) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    )
  }

  return (
    <FinancialDataProvider>
      <Layout>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/entities" element={<EntityIntegrationsPage />} />
          <Route path="/transactions" element={<TransactionsPage />} />
          <Route path="/investments" element={<InvestmentsPage />} />
          <Route
            path="/investments/stocks-etfs"
            element={<StocksInvestmentPage />}
          />
          <Route path="/investments/funds" element={<FundsInvestmentPage />} />
          <Route
            path="/investments/deposits"
            element={<DepositsInvestmentPage />}
          />
          <Route
            path="/investments/factoring"
            element={<FactoringInvestmentPage />}
          />
          <Route
            path="/investments/real-estate"
            element={<RealEstateCFInvestmentPage />}
          />
          <Route
            path="/investments/crypto"
            element={<CryptoInvestmentPage />}
          />
          <Route path="/export" element={<ExportPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>

      {/* Release Update Modal */}
      {showReleaseModal && updateInfo?.hasUpdate && updateInfo.release && (
        <ReleaseUpdateModal
          isOpen={showReleaseModal}
          onClose={handleCloseReleaseModal}
          currentVersion={updateInfo.currentVersion}
          latestVersion={updateInfo.latestVersion}
          release={updateInfo.release}
          platform={platform}
          onSkipVersion={handleSkipVersion}
        />
      )}
    </FinancialDataProvider>
  )
}

export default App
