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
  KeyRound,
  Sun,
  Moon,
  ChevronRight,
  ChevronLeft,
  Globe,
  FileUp,
  SunMoon,
  TrendingUp,
  ChevronDown,
  ChevronUp,
  ArrowLeftRight,
  Blocks,
  User,
  CalendarCog,
  CalendarSync,
  HandCoins,
  PiggyBank,
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
// Removed dynamic filtering for assets; all asset subsections always visible
import { getIconForProductType } from "@/utils/dashboardUtils"
import { usePinnedAssets } from "@/context/PinnedAssetsContext"

export function Sidebar() {
  const { t, locale, changeLocale } = useI18n()
  const { theme, setThemeMode } = useTheme()
  const { logout, startPasswordChange } = useAuth()
  const { platform } = useAppContext()
  useFinancialData() // still invoke to keep data fetching side-effects if any
  const { pinnedAssets } = usePinnedAssets()
  const navigate = useNavigate()
  const location = useLocation()

  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window !== "undefined") {
      return window.innerWidth < 768
    }
    return false
  })

  const [investmentsExpanded, setInvestmentsExpanded] = useState(() => {
    return location.pathname.startsWith("/investments")
  })

  const [managementExpanded, setManagementExpanded] = useState(() => {
    return location.pathname.startsWith("/management")
  })

  const investmentRoutes = useMemo(
    () => [
      {
        path: "/banking",
        label: t.banking.title,
        productType: ProductType.ACCOUNT,
        key: "banking",
      },
      {
        path: "/investments/stocks-etfs",
        label: t.common.stocksEtfs,
        productType: ProductType.STOCK_ETF,
        key: "stocks-etfs",
      },
      {
        path: "/investments/funds",
        label: t.common.fundsInvestments,
        productType: ProductType.FUND,
        key: "funds",
      },
      {
        path: "/investments/deposits",
        label: t.common.depositsInvestments,
        productType: ProductType.DEPOSIT,
        key: "deposits",
      },
      {
        path: "/investments/factoring",
        label: t.common.factoringInvestments,
        productType: ProductType.FACTORING,
        key: "factoring",
      },
      {
        path: "/investments/real-estate-cf",
        label: t.common.realEstateCfInvestments,
        productType: ProductType.REAL_ESTATE_CF,
        key: "real-estate-cf",
      },
      {
        path: "/investments/crypto",
        label: t.common.cryptoInvestments,
        productType: ProductType.CRYPTO,
        key: "crypto",
      },
      {
        path: "/real-estate",
        label: t.realEstate.title,
        productType: ProductType.REAL_ESTATE,
        key: "real-estate",
      },
    ],
    [t],
  )

  const managementRoutes = [
    {
      path: "/management/recurring",
      label: t.management.recurringMoney,
      icon: <CalendarSync className="h-4 w-4" />,
    },
    {
      path: "/management/pending",
      label: t.management.pendingMoney,
      icon: <HandCoins className="h-4 w-4" />,
    },
    {
      path: "/management/auto-contributions",
      label: t.management.autoContributions,
      icon: <PiggyBank className="h-4 w-4" />,
    },
  ]

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
    if (location.pathname.startsWith("/management")) {
      setManagementExpanded(true)
    }
  }, [location.pathname])

  const navItems = [
    {
      path: "/",
      label: t.common.dashboard,
      icon: <LayoutDashboard size={20} />,
    },
    // Banking & Real Estate now inside assets section (and can be pinned)
    {
      path: "/transactions",
      label: t.common.transactions,
      icon: <ArrowLeftRight size={20} />,
    },
    {
      path: "/entities",
      label: t.common.entities,
      icon: <Blocks size={20} />,
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

  const toggleManagement = () => {
    setManagementExpanded(!managementExpanded)
  }

  const handleLogout = async () => {
    try {
      await logout()
      navigate("/login")
    } catch (error) {
      console.error("Logout failed:", error)
    }
  }

  const handleChangePassword = async () => {
    try {
      await startPasswordChange()
      navigate("/login")
    } catch (error) {
      console.error("Change password flow failed:", error)
    }
  }

  return (
    <div
      className={cn(
        "h-screen min-h-0 flex flex-col bg-gray-100 dark:bg-black border-r border-gray-200 dark:border-gray-800 transition-all duration-300 overflow-hidden",
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

      <nav
        className={cn(
          "flex-1 min-h-0 overflow-y-auto py-4 no-scrollbar",
          collapsed ? "pl-1" : "",
        )}
      >
        {/* Extend content backgrounds under the scrollbar gutter */}
        <div className="pr-2 -mr-2">
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

            {/* Pinned assets */}
            {pinnedAssets.map(p => {
              const item = investmentRoutes.find(r => r.key === p)
              if (!item) return null
              return (
                <li key={`pinned-${p}`}>
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
                      {getIconForProductType(item.productType, "h-4 w-4")}
                      {!collapsed && <span className="ml-3">{item.label}</span>}
                    </span>
                  </Button>
                </li>
              )
            })}

            {/* Assets Section */}
            {investmentRoutes.length > 0 && (
              <li>
                <Button
                  variant="ghost"
                  className={cn(
                    "w-full rounded-none h-12",
                    collapsed ? "justify-center" : "justify-between",
                    (() => {
                      const isAssetPath =
                        location.pathname.startsWith("/investments") ||
                        location.pathname.startsWith("/banking") ||
                        location.pathname.startsWith("/real-estate")
                      if (!isAssetPath)
                        return "hover:bg-gray-200 dark:hover:bg-gray-900"
                      // If current route is a pinned asset root path, don't highlight section
                      const pinnedRouteMatch = investmentRoutes.find(
                        r =>
                          pinnedAssets.includes(r.key as any) &&
                          location.pathname === r.path,
                      )
                      if (pinnedRouteMatch) {
                        return "hover:bg-gray-200 dark:hover:bg-gray-900"
                      }
                      return "bg-gray-200 dark:bg-gray-900 text-primary"
                    })(),
                  )}
                  onClick={() => {
                    const isOnInvestmentsSubpage =
                      location.pathname.startsWith("/investments/")
                    const isOnInvestmentsPage =
                      location.pathname.endsWith("/investments")
                    if (
                      !collapsed &&
                      !isOnInvestmentsSubpage &&
                      isOnInvestmentsPage
                    ) {
                      toggleInvestments()
                    }
                    navigate("/investments")
                  }}
                >
                  <span className="flex items-center">
                    <TrendingUp size={20} />
                    {!collapsed && (
                      <span className="ml-3">
                        {t.common.myAssets || t.common.investments}
                      </span>
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

                {/* Asset Subsections (exclude pinned to avoid duplication) */}
                {!collapsed && investmentsExpanded && (
                  <ul className="mt-1 space-y-1">
                    {investmentRoutes
                      .filter(r => !pinnedAssets.includes(r.key as any))
                      .map(route => (
                        <li key={route.path}>
                          <Button
                            variant="ghost"
                            className={cn(
                              "w-full rounded-none h-10 pl-6",
                              "text-sm justify-start",
                              location.pathname === route.path
                                ? "bg-gray-200 dark:bg-gray-900 text-primary"
                                : "hover:bg-gray-200 dark:hover:bg-gray-900 text-gray-600 dark:text-gray-400",
                            )}
                            onClick={() => navigate(route.path)}
                          >
                            {getIconForProductType(
                              route.productType,
                              "h-4 w-4",
                            )}
                            <span className="ml-2">{route.label}</span>
                          </Button>
                        </li>
                      ))}
                  </ul>
                )}
              </li>
            )}

            {/* Management Section */}
            <li>
              <Button
                variant="ghost"
                className={cn(
                  "w-full rounded-none h-12",
                  collapsed ? "justify-center" : "justify-between",
                  location.pathname.startsWith("/management")
                    ? "bg-gray-200 dark:bg-gray-900 text-primary"
                    : "hover:bg-gray-200 dark:hover:bg-gray-900",
                )}
                onClick={() => {
                  const isOnManagementSubpage =
                    location.pathname.startsWith("/management/")
                  const isOnManagementPage =
                    location.pathname.endsWith("/management")
                  if (
                    !collapsed &&
                    !isOnManagementSubpage &&
                    isOnManagementPage
                  ) {
                    toggleManagement()
                  }
                  navigate("/management")
                }}
              >
                <span className="flex items-center">
                  <CalendarCog size={20} />
                  {!collapsed && (
                    <span className="ml-3">{t.management.title}</span>
                  )}
                </span>
                {!collapsed && managementRoutes.length > 0 && (
                  <span className="ml-auto">
                    {managementExpanded ? (
                      <ChevronUp size={16} />
                    ) : (
                      <ChevronDown size={16} />
                    )}
                  </span>
                )}
              </Button>

              {/* Management Subsections */}
              {!collapsed && managementExpanded && (
                <ul className="mt-1 space-y-1">
                  {managementRoutes.map(route => (
                    <li key={route.path}>
                      <Button
                        variant="ghost"
                        className={cn(
                          "w-full rounded-none h-10 pl-6",
                          "text-sm justify-start",
                          location.pathname === route.path
                            ? "bg-gray-200 dark:bg-gray-900 text-primary"
                            : "hover:bg-gray-200 dark:hover:bg-gray-900 text-gray-600 dark:text-gray-400",
                        )}
                        onClick={() => navigate(route.path)}
                      >
                        {route.icon}
                        <span className="ml-2">{route.label}</span>
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </li>

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
        </div>
      </nav>

      <div className="p-4 border-t border-gray-200 dark:border-gray-800">
        {!collapsed ? (
          <div className="space-y-2">
            <div className="flex gap-1">
              <Popover>
                <PopoverTrigger asChild>
                  <Button variant="ghost" className="flex-1" size="sm">
                    <Globe size={16} className="mr-2" />
                    {languages.find(lang => lang.code === locale)?.label}
                  </Button>
                </PopoverTrigger>
                <PopoverContent side="top" className="p-1 w-auto">
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
                  <Button variant="ghost" className="flex-1" size="sm">
                    {theme === "light" && <Sun size={16} />}
                    {theme === "dark" && <Moon size={16} />}
                    {theme === "system" && <SunMoon size={16} />}
                  </Button>
                </PopoverTrigger>
                <PopoverContent side="top" className="p-1 w-auto">
                  <div className="flex flex-col gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setThemeMode("light")}
                      disabled={theme === "light"}
                    >
                      <Sun size={16} className="mr-2" /> Light
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setThemeMode("dark")}
                      disabled={theme === "dark"}
                    >
                      <Moon size={16} className="mr-2" /> Dark
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setThemeMode("system")}
                      disabled={theme === "system"}
                    >
                      <SunMoon size={16} className="mr-2" /> System
                    </Button>
                  </div>
                </PopoverContent>
              </Popover>
              <Popover>
                <PopoverTrigger asChild>
                  <Button variant="ghost" className="flex-1" size="sm">
                    <User size={16} />
                  </Button>
                </PopoverTrigger>
                <PopoverContent side="top" className="p-1 w-auto">
                  <div className="flex flex-col gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="justify-start"
                      onClick={handleChangePassword}
                    >
                      <KeyRound size={16} className="mr-2" />
                      {t.login.changePassword}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 justify-start"
                      onClick={handleLogout}
                    >
                      <LogOut size={16} className="mr-2" />
                      {t.common.logout}
                    </Button>
                  </div>
                </PopoverContent>
              </Popover>
            </div>
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
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="ghost" size="icon" className="w-full">
                  <User size={20} />
                </Button>
              </PopoverTrigger>
              <PopoverContent side="right" className="p-1 w-auto">
                <div className="flex flex-col gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="justify-start"
                    onClick={handleChangePassword}
                  >
                    <KeyRound size={18} className="mr-2" />
                    {t.login.changePassword}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 justify-start"
                    onClick={handleLogout}
                  >
                    <LogOut size={18} className="mr-2" />
                    {t.common.logout}
                  </Button>
                </div>
              </PopoverContent>
            </Popover>
          </div>
        )}
      </div>
    </div>
  )
}
