import React from "react"
import { useI18n } from "@/i18n"
import { useNavigate } from "react-router-dom"
import { Card } from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { CalendarSync, HandCoins, PiggyBank } from "lucide-react"

export default function ManagementPage() {
  const { t } = useI18n()
  const navigate = useNavigate()

  const managementRoutes = [
    {
      path: "/management/recurring",
      label: t.management.recurringMoney,
      icon: <CalendarSync className="h-6 w-6" />,
      color: "bg-blue-100 text-blue-600 dark:bg-blue-900 dark:text-blue-300",
      description: t.management.recurringMoneyDescription,
    },
    {
      path: "/management/pending",
      label: t.management.pendingMoney,
      icon: <HandCoins className="h-6 w-6" />,
      color:
        "bg-green-100 text-green-600 dark:bg-green-900 dark:text-green-300",
      description: t.management.pendingMoneyDescription,
    },
    {
      path: "/management/auto-contributions",
      label: t.management.autoContributions,
      icon: <PiggyBank className="h-6 w-6" />,
      color: "bg-pink-100 text-pink-600 dark:bg-pink-900 dark:text-pink-300",
      description: t.management.autoContributionsDescription,
    },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t.management.title}</h1>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {managementRoutes.map(route => (
          <Card
            key={route.path}
            className="p-6 transition-all cursor-pointer hover:shadow-lg"
            onClick={() => navigate(route.path)}
          >
            <div className="flex items-center space-x-4">
              <div className={`p-3 rounded-lg ${route.color}`}>
                {route.icon}
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                  {route.label}
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                  {route.description}
                </p>
                <Button
                  variant="ghost"
                  size="sm"
                  className="mt-3 p-0 h-auto text-primary hover:text-primary/80"
                  onClick={e => {
                    e.stopPropagation()
                    navigate(route.path)
                  }}
                >
                  {t.common.viewDetails} →
                </Button>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}
