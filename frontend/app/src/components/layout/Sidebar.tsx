import { useNavigate, useLocation } from "react-router-dom"
import { useI18n } from "@/i18n"
import { useTheme } from "@/context/ThemeContext"
import { useAuth } from "@/context/AuthContext"
import { useAppContext } from "@/context/AppContext"
import { useFinancialData } from "@/context/FinancialDataContext"
import { cn } from "@/lib/utils"
import {
  LayoutDashboard,
  Settings,
  LogOut,
  Sun,
  Moon,
  ChevronRight,
  ChevronLeft,
  Globe,
  FileUp,
  SunMoon,
  Receipt,
  BanknoteArrowDown,
  TrendingUp,
  ChevronDown,
  ChevronUp,
} from "lucide-react"
import { useState, useEffect, useMemo } from "react"
import { Button } from "@/components/ui/Button"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import type { Locale } from "@/i18n"
import { PlatformType } from "@/types"
import { ProductType } from "@/types/position"
import { getAvailableInvestmentTypes } from "@/utils/financialDataUtils"

export function Sidebar() {
  const { t, locale, changeLocale } = useI18n()
  const { theme, setThemeMode } = useTheme()
  const { logout } = useAuth()
  const { platform } = useAppContext()
  const { positionsData } = useFinancialData()
  const navigate = useNavigate()
  const location = useLocation()

  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window !== "undefined") {
      return window.innerWidth < 768
    }
    return false
  })

  const [investmentsExpanded, setInvestmentsExpanded] = useState(() => {
    // Expand investments section if we're on an investment page
    return location.pathname.startsWith("/investments")
  })

  // Get available investment types for the user
  const availableInvestmentTypes = useMemo(() => {
    return getAvailableInvestmentTypes(positionsData)
  }, [positionsData])

  // Define investment subsections with their routes and labels
  const investmentRoutes = useMemo(() => {
    const routes = []

    if (availableInvestmentTypes.includes(ProductType.STOCK_ETF)) {
      routes.push({
        path: "/investments/stocks-etfs",
        label: t.common.stocksEtfs,
        productType: ProductType.STOCK_ETF,
      })
    }

    if (availableInvestmentTypes.includes(ProductType.FUND)) {
      routes.push({
        path: "/investments/funds",
        label: t.common.fundsInvestments,
        productType: ProductType.FUND,
      })
    }

    if (availableInvestmentTypes.includes(ProductType.DEPOSIT)) {
      routes.push({
        path: "/investments/deposits",
        label: t.common.depositsInvestments,
        productType: ProductType.DEPOSIT,
      })
    }

    if (availableInvestmentTypes.includes(ProductType.FACTORING)) {
      routes.push({
        path: "/investments/factoring",
        label: t.common.factoringInvestments,
        productType: ProductType.FACTORING,
      })
    }

    if (availableInvestmentTypes.includes(ProductType.REAL_ESTATE_CF)) {
      routes.push({
        path: "/investments/real-estate",
        label: t.common.realEstateCfInvestments,
        productType: ProductType.REAL_ESTATE_CF,
      })
    }

    if (availableInvestmentTypes.includes(ProductType.CRYPTO)) {
      routes.push({
        path: "/investments/crypto",
        label: t.common.cryptoInvestments,
        productType: ProductType.CRYPTO,
      })
    }

    return routes
  }, [availableInvestmentTypes, t.common])

  useEffect(() => {
    const handleResize = () => {
      const isNarrowView = window.innerWidth < 768
      if (isNarrowView && !collapsed) {
        setCollapsed(true)
      }
    }

    window.addEventListener("resize", handleResize)
    return () => window.removeEventListener("resize", handleResize)
  }, [collapsed])

  // Update investments expanded state when navigating
  useEffect(() => {
    if (location.pathname.startsWith("/investments")) {
      setInvestmentsExpanded(true)
    }
  }, [location.pathname])

  const navItems = [
    {
      path: "/",
      label: t.common.dashboard,
      icon: <LayoutDashboard size={20} />,
    },
    {
      path: "/transactions",
      label: t.common.transactions,
      icon: <Receipt size={20} />,
    },
    {
      path: "/entities",
      label: t.common.entities,
      icon: <BanknoteArrowDown size={20} />,
    },
    { path: "/export", label: t.export.title, icon: <FileUp size={20} /> },
    {
      path: "/settings",
      label: t.common.settings,
      icon: <Settings size={20} />,
    },
  ]

  const languages: { code: Locale; label: string }[] = [
    { code: "en-US", label: "EN" },
    { code: "es-ES", label: "ES" },
  ]

  const toggleSidebar = () => {
    setCollapsed(!collapsed)
  }

  const toggleInvestments = () => {
    setInvestmentsExpanded(!investmentsExpanded)
  }

  const handleLogout = async () => {
    try {
      await logout()
      navigate("/login")
    } catch (error) {
      console.error("Logout failed:", error)
    }
  }

  return (
    <div
      className={cn(
        "h-screen flex flex-col bg-gray-100 dark:bg-black border-r border-gray-200 dark:border-gray-800 transition-all duration-300",
        collapsed ? "w-16" : "w-64",
        platform === PlatformType.MAC ? "pt-4" : "",
      )}
    >
      <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-800">
        {!collapsed && <h1 className="text-xl font-bold">Finanze</h1>}
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleSidebar}
          className={collapsed ? "mx-auto" : "ml-auto"}
        >
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </Button>
      </div>

      <nav className="flex-1 py-4">
        <ul className="space-y-1">
          {/* Dashboard */}
          <li>
            <Button
              variant="ghost"
              className={cn(
                "w-full rounded-none h-12",
                collapsed ? "justify-center" : "justify-start",
                location.pathname === "/"
                  ? "bg-gray-200 dark:bg-gray-900 text-primary"
                  : "hover:bg-gray-200 dark:hover:bg-gray-900",
              )}
              onClick={() => navigate("/")}
            >
              <span className="flex items-center">
                <LayoutDashboard size={20} />
                {!collapsed && (
                  <span className="ml-3">{t.common.dashboard}</span>
                )}
              </span>
            </Button>
          </li>

          {/* Investments Section */}
          {investmentRoutes.length > 0 && (
            <li>
              <Button
                variant="ghost"
                className={cn(
                  "w-full rounded-none h-12",
                  collapsed ? "justify-center" : "justify-between",
                  location.pathname.startsWith("/investments")
                    ? "bg-gray-200 dark:bg-gray-900 text-primary"
                    : "hover:bg-gray-200 dark:hover:bg-gray-900",
                )}
                onClick={
                  collapsed ? () => navigate("/investments") : toggleInvestments
                }
              >
                <span className="flex items-center">
                  <TrendingUp size={20} />
                  {!collapsed && (
                    <span className="ml-3">{t.common.investments}</span>
                  )}
                </span>
                {!collapsed && investmentRoutes.length > 0 && (
                  <span className="ml-auto">
                    {investmentsExpanded ? (
                      <ChevronUp size={16} />
                    ) : (
                      <ChevronDown size={16} />
                    )}
                  </span>
                )}
              </Button>

              {/* Investment Subsections */}
              {!collapsed && investmentsExpanded && (
                <ul className="mt-1 space-y-1">
                  {investmentRoutes.map(route => (
                    <li key={route.path}>
                      <Button
                        variant="ghost"
                        className={cn(
                          "w-full rounded-none h-10 pl-12",
                          "text-sm justify-start",
                          location.pathname === route.path
                            ? "bg-gray-300 dark:bg-gray-800 text-primary"
                            : "hover:bg-gray-200 dark:hover:bg-gray-900 text-gray-600 dark:text-gray-400",
                        )}
                        onClick={() => navigate(route.path)}
                      >
                        {route.label}
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          )}

          {/* Other navigation items */}
          {navItems.slice(1).map(item => (
            <li key={item.path}>
              <Button
                variant="ghost"
                className={cn(
                  "w-full rounded-none h-12",
                  collapsed ? "justify-center" : "justify-start",
                  location.pathname === item.path
                    ? "bg-gray-200 dark:bg-gray-900 text-primary"
                    : "hover:bg-gray-200 dark:hover:bg-gray-900",
                )}
                onClick={() => navigate(item.path)}
              >
                <span className="flex items-center">
                  {item.icon}
                  {!collapsed && <span className="ml-3">{item.label}</span>}
                </span>
              </Button>
            </li>
          ))}
        </ul>
      </nav>

      <div className="p-4 border-t border-gray-200 dark:border-gray-800">
        {!collapsed ? (
          <div className="space-y-2">
            <div className="flex flex-wrap gap-1 mb-2">
              {languages.map(lang => (
                <Button
                  key={lang.code}
                  variant={locale === lang.code ? "default" : "outline"}
                  size="sm"
                  className="flex-1"
                  onClick={() => changeLocale(lang.code)}
                >
                  {lang.label}
                </Button>
              ))}
            </div>
            <div className="flex gap-1">
              <Button
                variant="ghost"
                className="flex-1"
                onClick={() => setThemeMode("light")}
                disabled={theme === "light"}
              >
                <Sun size={18} />
              </Button>
              <Button
                variant="ghost"
                className="flex-1"
                onClick={() => setThemeMode("dark")}
                disabled={theme === "dark"}
              >
                <Moon size={18} />
              </Button>
              <Button
                variant="ghost"
                className="flex-1"
                onClick={() => setThemeMode("system")}
                disabled={theme === "system"}
              >
                <SunMoon size={18} />
              </Button>
            </div>
            <Button
              variant="ghost"
              className="w-full text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 justify-start"
              onClick={handleLogout}
            >
              <LogOut size={18} className="mr-2" />
              {t.common.logout}
            </Button>
          </div>
        ) : (
          <div className="space-y-2">
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="ghost" size="icon" className="w-full">
                  <Globe size={20} />
                </Button>
              </PopoverTrigger>
              <PopoverContent side="right" className="p-1 w-auto">
                <div className="flex flex-col gap-1">
                  {languages.map(lang => (
                    <Button
                      key={lang.code}
                      variant={locale === lang.code ? "default" : "outline"}
                      size="sm"
                      onClick={() => changeLocale(lang.code)}
                    >
                      {lang.label}
                    </Button>
                  ))}
                </div>
              </PopoverContent>
            </Popover>
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="ghost" size="icon" className="w-full">
                  {theme === "light" && <Sun size={20} />}
                  {theme === "dark" && <Moon size={20} />}
                  {theme === "system" && <SunMoon size={20} />}
                </Button>
              </PopoverTrigger>
              <PopoverContent side="right" className="p-1 w-auto">
                <div className="flex flex-col gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setThemeMode("light")}
                    disabled={theme === "light"}
                  >
                    <Sun size={18} className="mr-2" /> Light
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setThemeMode("dark")}
                    disabled={theme === "dark"}
                  >
                    <Moon size={18} className="mr-2" /> Dark
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setThemeMode("system")}
                    disabled={theme === "system"}
                  >
                    <SunMoon size={18} className="mr-2" /> System
                  </Button>
                </div>
              </PopoverContent>
            </Popover>
            <Button
              variant="ghost"
              size="icon"
              className="w-full text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
              onClick={handleLogout}
            >
              <LogOut size={20} />
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
