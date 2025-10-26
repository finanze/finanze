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
import { useState, useEffect, useMemo, useRef } from "react"
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
  const { positionsData, realEstateList } = useFinancialData()
  const { pinnedAssets } = usePinnedAssets()
  const navigate = useNavigate()
  const location = useLocation()

  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window !== "undefined") {
      return window.innerWidth < 768
    }
    return false
  })

  const [isNarrowView, setIsNarrowView] = useState(() => {
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

  const investmentRoutes = useMemo(() => {
    const hasProductEntries = (pt: ProductType) => {
      if (!positionsData?.positions) return false
      return Object.values(positionsData.positions).some((entity: any) => {
        const product = entity.products[pt]
        if (!product) return false
        if (product.entries && product.entries.length > 0) return true
        // some product structures might store positions differently; fallback checks
        return Array.isArray(product) && product.length > 0
      })
    }
    const routes = [
      {
        path: "/banking",
        label: t.banking.title,
        productType: ProductType.ACCOUNT,
        key: "banking",
        hasData:
          hasProductEntries(ProductType.ACCOUNT) ||
          hasProductEntries(ProductType.CARD) ||
          hasProductEntries(ProductType.LOAN),
      },
      {
        path: "/investments/stocks-etfs",
        label: t.common.stocksEtfs,
        productType: ProductType.STOCK_ETF,
        key: "stocks-etfs",
        hasData: hasProductEntries(ProductType.STOCK_ETF),
      },
      {
        path: "/investments/funds",
        label: t.common.fundsInvestments,
        productType: ProductType.FUND,
        key: "funds",
        hasData: hasProductEntries(ProductType.FUND),
      },
      {
        path: "/investments/deposits",
        label: t.common.depositsInvestments,
        productType: ProductType.DEPOSIT,
        key: "deposits",
        hasData: hasProductEntries(ProductType.DEPOSIT),
      },
      {
        path: "/investments/factoring",
        label: t.common.factoringInvestments,
        productType: ProductType.FACTORING,
        key: "factoring",
        hasData: hasProductEntries(ProductType.FACTORING),
      },
      {
        path: "/investments/real-estate-cf",
        label: t.common.realEstateCfInvestments,
        productType: ProductType.REAL_ESTATE_CF,
        key: "real-estate-cf",
        hasData: hasProductEntries(ProductType.REAL_ESTATE_CF),
      },
      {
        path: "/investments/crypto",
        label: t.common.cryptoInvestments,
        productType: ProductType.CRYPTO,
        key: "crypto",
        hasData: hasProductEntries(ProductType.CRYPTO),
      },
      {
        path: "/investments/commodities",
        label: t.common.commodities,
        productType: ProductType.COMMODITY,
        key: "commodities",
        hasData: hasProductEntries(ProductType.COMMODITY),
      },
      {
        path: "/real-estate",
        label: t.realEstate.title,
        productType: ProductType.REAL_ESTATE,
        key: "real-estate",
        hasData: (realEstateList?.length || 0) > 0,
      },
    ]
    return routes
  }, [t, positionsData, realEstateList])

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

  const wasNarrowRef = useRef(isNarrowView)

  useEffect(() => {
    const handleResize = () => {
      if (typeof window === "undefined") return
      const narrow = window.innerWidth < 768
      setIsNarrowView(narrow)
      if (narrow && !wasNarrowRef.current) {
        setCollapsed(true)
      }
      wasNarrowRef.current = narrow
    }

    handleResize()
    window.addEventListener("resize", handleResize)
    return () => window.removeEventListener("resize", handleResize)
  }, [])

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

  const overlayVisible = isNarrowView && !collapsed
  const containerWidthClass = collapsed
    ? "w-16"
    : overlayVisible
      ? "w-16"
      : "w-64"
  const containerClass = cn(
    "relative h-screen flex-shrink-0",
    overlayVisible ? "" : "transition-all duration-300",
    containerWidthClass,
  )
  const baseSidebarClass = cn(
    "h-screen min-h-0 flex flex-col bg-gray-100 dark:bg-black border-r border-gray-200 dark:border-gray-800 overflow-hidden",
    platform === PlatformType.MAC ? "pt-4" : "",
  )

  const sidebarClass = overlayVisible
    ? cn(
        baseSidebarClass,
        "fixed inset-y-0 left-0 z-40 w-64 shadow-2xl transition-none",
      )
    : cn(baseSidebarClass, "relative w-full transition-all duration-300")

  return (
    <div className={containerClass}>
      <div className={sidebarClass}>
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
                        {getIconForProductType(item.productType, "h-5 w-5")}
                        {!collapsed && (
                          <span className="ml-3">{item.label}</span>
                        )}
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
                                  : route.hasData
                                    ? "hover:bg-gray-200 dark:hover:bg-gray-900 text-gray-600 dark:text-gray-400"
                                    : "opacity-50 text-gray-400 dark:text-gray-600 hover:bg-gray-200 dark:hover:bg-gray-900",
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
                        <Sun size={16} className="mr-2" /> {t.common.light}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setThemeMode("dark")}
                        disabled={theme === "dark"}
                      >
                        <Moon size={16} className="mr-2" /> {t.common.dark}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setThemeMode("system")}
                        disabled={theme === "system"}
                      >
                        <SunMoon size={16} className="mr-2" /> {t.common.system}
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
                      <Sun size={18} className="mr-2" /> {t.common.light}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setThemeMode("dark")}
                      disabled={theme === "dark"}
                    >
                      <Moon size={18} className="mr-2" /> {t.common.dark}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setThemeMode("system")}
                      disabled={theme === "system"}
                    >
                      <SunMoon size={18} className="mr-2" /> {t.common.system}
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
      {overlayVisible ? (
        <button
          type="button"
          className="fixed inset-0 z-30 bg-black/40"
          onClick={toggleSidebar}
          aria-label={t.common.close}
        />
      ) : null}
    </div>
  )
}
