import { useNavigate, useLocation } from "react-router-dom"
import { useI18n } from "@/i18n"
import { useTheme } from "@/context/ThemeContext"
import { useAuth } from "@/context/AuthContext"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useCloud } from "@/context/CloudContext"
import { cn } from "@/lib/utils"
import {
  LayoutDashboard,
  LogOut,
  KeyRound,
  Sun,
  Moon,
  ChevronRight,
  ChevronLeft,
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
  Settings,
  LucideIcon,
  Calculator,
} from "lucide-react"
import { useState, useEffect, useMemo, useRef } from "react"
import { Button } from "@/components/ui/Button"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import { PlatformType, CloudRole } from "@/types"
import { ProductType } from "@/types/position"
import { getIconForProductType } from "@/utils/dashboardUtils"
import {
  usePinnedShortcuts,
  type PinnedShortcutId,
} from "@/context/PinnedShortcutsContext"
import { BackupStatusPopover } from "@/components/layout/BackupStatusPopover"
import { getPlatformType, isNativeMobile } from "@/lib/platform"

export function Sidebar() {
  const { t } = useI18n()
  const { theme, setThemeMode } = useTheme()
  const { logout, startPasswordChange } = useAuth()
  const { positionsData, realEstateList } = useFinancialData()
  const { pinnedShortcuts } = usePinnedShortcuts()
  const { role, permissions } = useCloud()
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

  type ManagementRoute = {
    path: string
    label: string
    Icon: LucideIcon
    key: PinnedShortcutId
  }

  const managementRoutes = useMemo<ManagementRoute[]>(
    () => [
      {
        path: "/management/recurring",
        label: t.management.recurringMoney,
        Icon: CalendarSync,
        key: "management-recurring",
      },
      {
        path: "/management/pending",
        label: t.management.pendingMoney,
        Icon: HandCoins,
        key: "management-pending",
      },
      {
        path: "/management/auto-contributions",
        label: t.management.autoContributions,
        Icon: PiggyBank,
        key: "management-auto-contributions",
      },
    ],
    [
      t.management.recurringMoney,
      t.management.pendingMoney,
      t.management.autoContributions,
    ],
  )

  const unpinnedManagementRoutes = useMemo(
    () =>
      managementRoutes.filter(route => !pinnedShortcuts.includes(route.key)),
    [managementRoutes, pinnedShortcuts],
  )

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

  useEffect(() => {
    const isPinnedRoute = pinnedShortcuts.some(pinnedKey => {
      const investmentRoute = investmentRoutes.find(r => r.key === pinnedKey)
      const managementRoute = managementRoutes.find(r => r.key === pinnedKey)
      const route = investmentRoute ?? managementRoute
      return route?.path === location.pathname
    })

    if (isPinnedRoute) return

    if (location.pathname.startsWith("/investments")) {
      setInvestmentsExpanded(true)
    }
    if (location.pathname.startsWith("/management")) {
      setManagementExpanded(true)
    }
  }, [location.pathname, pinnedShortcuts, investmentRoutes, managementRoutes])

  const navItems = [
    {
      path: "/",
      label: t.common.dashboard,
      icon: <LayoutDashboard size={20} />,
    },
    {
      path: "/transactions",
      label: t.common.transactions,
      icon: <ArrowLeftRight size={20} />,
    },
    {
      path: "/calculations",
      label: t.calculations.title,
      icon: <Calculator size={20} />,
    },
    {
      path: "/entities",
      label: t.common.entities,
      icon: <Blocks size={20} />,
    },
    { path: "/export", label: t.export.title, icon: <FileUp size={20} /> },
  ]

  const platform = getPlatformType()

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
    "relative h-screen flex-shrink-0 overflow-x-hidden",
    overlayVisible ? "" : "transition-all duration-300",
    containerWidthClass,
  )
  const baseSidebarClass = cn(
    "h-screen min-h-0 flex flex-col bg-gray-100 dark:bg-black border-r border-gray-200 dark:border-gray-800 overflow-hidden",
    platform === PlatformType.MAC ? "pt-4" : "",
    isNativeMobile() && "pt-[max(12px,var(--safe-area-inset-top,0px))]",
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
          {!collapsed && (
            <div className="flex items-center gap-2">
              <h1
                className={cn(
                  "text-xl font-bold",
                  role === CloudRole.PLUS &&
                    "bg-gradient-to-r from-amber-500 to-orange-500 bg-clip-text text-transparent",
                )}
              >
                Finanze
              </h1>
            </div>
          )}
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
              {pinnedShortcuts.map(p => {
                const investmentItem = investmentRoutes.find(r => r.key === p)
                const managementItem = managementRoutes.find(r => r.key === p)
                const item = investmentItem ?? managementItem
                if (!item) return null
                const icon = investmentItem
                  ? getIconForProductType(investmentItem.productType, "h-5 w-5")
                  : (() => {
                      const Icon = managementItem!.Icon
                      return <Icon className="h-5 w-5" />
                    })()
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
                        {icon}
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
                            pinnedShortcuts.includes(
                              r.key as PinnedShortcutId,
                            ) && location.pathname === r.path,
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
                        .filter(
                          r =>
                            !pinnedShortcuts.includes(
                              r.key as PinnedShortcutId,
                            ) && r.hasData,
                        )
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
              {unpinnedManagementRoutes.length > 0 && (
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
                    {!collapsed && (
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
                      {unpinnedManagementRoutes.map(route => (
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
                            <route.Icon className="h-4 w-4" />
                            <span className="ml-2">{route.label}</span>
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
          </div>
        </nav>

        <div className="p-4 border-t border-gray-200 dark:border-gray-800">
          {!collapsed ? (
            <div className="space-y-2">
              <div className="flex gap-1">
                <Button
                  variant="ghost"
                  className="flex-1"
                  size="sm"
                  onClick={() => navigate("/settings")}
                  aria-label={t.common.settings}
                >
                  <Settings size={18} strokeWidth={2.5} />
                </Button>
                {permissions.includes("backup.info") && (
                  <BackupStatusPopover collapsed={collapsed} />
                )}
                <Popover>
                  <PopoverTrigger asChild>
                    <Button
                      variant="ghost"
                      className="flex-1"
                      size="sm"
                      aria-label={t.common.darkMode}
                    >
                      {theme === "light" && (
                        <Sun size={18} fill="currentColor" />
                      )}
                      {theme === "dark" && (
                        <Moon size={18} fill="currentColor" />
                      )}
                      {theme === "system" && (
                        <SunMoon size={18} fill="currentColor" />
                      )}
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
                    <Button
                      variant="ghost"
                      className="flex-1"
                      size="sm"
                      aria-label={t.common.logout}
                    >
                      <User size={18} fill="currentColor" />
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
              <Button
                variant="ghost"
                size="icon"
                className="w-full"
                onClick={() => navigate("/settings")}
                aria-label={t.common.settings}
              >
                <Settings size={18} strokeWidth={2.5} />
              </Button>
              {permissions.includes("backup.info") && (
                <BackupStatusPopover collapsed={collapsed} />
              )}
              <Popover>
                <PopoverTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="w-full"
                    aria-label={t.common.darkMode}
                  >
                    {theme === "light" && <Sun size={18} fill="currentColor" />}
                    {theme === "dark" && <Moon size={18} fill="currentColor" />}
                    {theme === "system" && (
                      <SunMoon size={18} fill="currentColor" />
                    )}
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
                  <Button
                    variant="ghost"
                    size="icon"
                    className="w-full"
                    aria-label={t.common.logout}
                  >
                    <User size={18} fill="currentColor" />
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
