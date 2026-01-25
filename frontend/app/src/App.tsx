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
import CommoditiesInvestmentPage from "./pages/CommoditiesInvestmentPage"
import InvestmentsPage from "./pages/InvestmentsPage"
import BankingPage from "./pages/BankingPage"
import RealEstatePage from "./pages/RealEstatePage"
import RealEstateDetailsPage from "./pages/RealEstateDetailsPage"
import LoginPage from "./pages/LoginPage"
import RecurringMoneyPage from "./pages/RecurringMoneyPage"
import PendingMoneyPage from "./pages/PendingMoneyPage"
import AutoContributionsPage from "./pages/AutoContributionsPage"
import ManagementPage from "./pages/ManagementPage"
import CalculationsPage from "./pages/CalculationsPage"
import { useAuth } from "./context/AuthContext"
import SplashScreen from "./components/SplashScreen"
import { FinancialDataProvider } from "./context/FinancialDataContext"
import { PinnedShortcutsProvider } from "./context/PinnedShortcutsContext"
import { ReleaseUpdateModal } from "./components/ReleaseUpdateModal"
import { GlobalEntityModals } from "./components/GlobalEntityModals"
import { useReleaseUpdate } from "./hooks/useReleaseUpdate"
import { useAppContext } from "./context/AppContext"
import { EntityWorkflowProvider } from "./context/EntityWorkflowContext"
import { useState, useEffect } from "react"
import { useAutoUpdater } from "./hooks/useAutoUpdater"
import { hideSplashScreen as hideMobileSplashScreen } from "@/lib/mobile"

function App() {
  const { isAuthenticated, isInitializing } = useAuth()
  const { platform } = useAppContext()
  const [showReleaseModal, setShowReleaseModal] = useState(false)
  const [skippedVersions, setSkippedVersions] = useState<string[]>([])
  const {
    state: autoUpdateState,
    downloadUpdate: startAutoUpdateDownload,
    quitAndInstall: startAutoUpdateInstallation,
  } = useAutoUpdater({
    checkOnMount: isAuthenticated && !isInitializing,
  })

  // Hide the native/mobile splash screen once the app is ready to render UI.
  useEffect(() => {
    if (!isInitializing) {
      hideMobileSplashScreen()
    }
  }, [isInitializing])

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

  useEffect(() => {
    if (
      isAuthenticated &&
      autoUpdateState.isSupported &&
      autoUpdateState.updateInfo &&
      !showReleaseModal
    ) {
      setShowReleaseModal(true)
    }
  }, [
    autoUpdateState.isSupported,
    autoUpdateState.updateInfo,
    isAuthenticated,
    showReleaseModal,
  ])

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
    <EntityWorkflowProvider>
      <FinancialDataProvider>
        <PinnedShortcutsProvider>
          <Layout>
            <Routes>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/banking" element={<BankingPage />} />
              <Route path="/real-estate" element={<RealEstatePage />} />
              <Route
                path="/real-estate/:id"
                element={<RealEstateDetailsPage />}
              />
              <Route path="/entities" element={<EntityIntegrationsPage />} />
              <Route path="/transactions" element={<TransactionsPage />} />
              <Route path="/investments" element={<InvestmentsPage />} />
              <Route
                path="/investments/stocks-etfs"
                element={<StocksInvestmentPage />}
              />
              <Route
                path="/investments/funds"
                element={<FundsInvestmentPage />}
              />
              <Route
                path="/investments/deposits"
                element={<DepositsInvestmentPage />}
              />
              <Route
                path="/investments/factoring"
                element={<FactoringInvestmentPage />}
              />
              <Route
                path="/investments/real-estate-cf"
                element={<RealEstateCFInvestmentPage />}
              />
              <Route
                path="/investments/crypto"
                element={<CryptoInvestmentPage />}
              />
              <Route
                path="/investments/commodities"
                element={<CommoditiesInvestmentPage />}
              />
              <Route path="/management" element={<ManagementPage />} />
              <Route
                path="/management/recurring"
                element={<RecurringMoneyPage />}
              />
              <Route
                path="/management/pending"
                element={<PendingMoneyPage />}
              />
              <Route
                path="/management/auto-contributions"
                element={<AutoContributionsPage />}
              />
              <Route path="/calculations" element={<CalculationsPage />} />
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
              autoUpdateSupported={autoUpdateState.isSupported}
              isAutoUpdateDownloading={autoUpdateState.isDownloading}
              autoUpdateProgress={autoUpdateState.progress}
              autoUpdateDownloadedBytes={autoUpdateState.downloadedBytes}
              autoUpdateTotalBytes={autoUpdateState.totalBytes}
              isAutoUpdateDownloaded={autoUpdateState.isDownloaded}
              autoUpdateErrorMessage={autoUpdateState.error?.message ?? null}
              onStartAutoUpdate={() => {
                void startAutoUpdateDownload()
              }}
              onInstallAutoUpdate={() => {
                void startAutoUpdateInstallation()
              }}
            />
          )}

          <GlobalEntityModals />
        </PinnedShortcutsProvider>
      </FinancialDataProvider>
    </EntityWorkflowProvider>
  )
}

export default App
