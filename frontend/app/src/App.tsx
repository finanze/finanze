import { Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from '@/components/layout/Layout'
import EntityIntegrationsPage from './pages/EntityIntegrationsPage'
import DashboardPage from './pages/DashboardPage'
import SettingsPage from './pages/SettingsPage'
import ExportPage from './pages/ExportPage'
import LoginPage from './pages/LoginPage'
import { useAuth } from './context/AuthContext'
import SplashScreen from './components/SplashScreen'
import { FinancialDataProvider } from './context/FinancialDataContext'

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
                    <Route
                        path="/entities"
                        element={<EntityIntegrationsPage />}
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
