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

function App() {
  const { isAuthenticated, isInitializing } = useAuth()

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
    </FinancialDataProvider>
  )
}

export default App
