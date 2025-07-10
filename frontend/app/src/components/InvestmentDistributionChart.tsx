import React from "react"
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts"
import { Card } from "@/components/ui/Card"
import { formatCurrency } from "@/lib/formatters"

interface ChartDataItem {
  name: string
  value: number
  color: string
  percentage: number
  currency?: string
  convertedValue?: number
  convertedCurrency?: string
}

interface InvestmentDistributionChartProps {
  data: ChartDataItem[]
  title: string
  locale?: string
  currency?: string
  showOriginalCurrency?: boolean
}

const RADIAN = Math.PI / 180
const renderCustomizedLabel = ({
  cx,
  cy,
  midAngle,
  innerRadius,
  outerRadius,
  percent,
}: any) => {
  if (percent < 0.03) return null // Don't show labels for slices smaller than 3%

  const percentage = percent * 100
  const isLargeSegment = percentage >= 15
  const radius = isLargeSegment
    ? innerRadius + (outerRadius - innerRadius) * 0.35 // More inner
    : innerRadius + (outerRadius - innerRadius) * 1.25 // Outside

  const x = cx + radius * Math.cos(-midAngle * RADIAN)
  const y = cy + radius * Math.sin(-midAngle * RADIAN)

  return (
    <text
      x={x}
      y={y}
      fill={isLargeSegment ? "white" : "currentColor"}
      textAnchor={x > cx ? "start" : "end"}
      dominantBaseline="central"
      className={`text-xs font-medium ${isLargeSegment ? "" : "text-gray-700 dark:text-gray-300"}`}
    >
      {`${percentage.toFixed(0)}%`}
    </text>
  )
}

const CustomTooltip = ({
  active,
  payload,
  locale,
  currency,
  showOriginalCurrency = false,
}: any) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload
    return (
      <div className="bg-popover border border-border rounded-lg shadow-lg p-3 max-w-xs">
        <p className="font-medium">{data.name}</p>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          {data.percentage.toFixed(2)}% •{" "}
          {showOriginalCurrency && data.currency && data.currency !== currency
            ? `${formatCurrency(data.value, locale, data.currency)} (${formatCurrency(data.convertedValue || data.value, locale, currency)})`
            : formatCurrency(data.value, locale, data.currency || currency)}
        </p>
      </div>
    )
  }
  return null
}

export const InvestmentDistributionChart: React.FC<
  InvestmentDistributionChartProps
> = ({
  data,
  title,
  locale = "en",
  currency = "USD",
  showOriginalCurrency = false,
}) => {
  if (!data || data.length === 0) {
    return (
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">{title}</h3>
        <div className="flex items-center justify-center h-64 text-gray-500 dark:text-gray-400">
          No data available
        </div>
      </Card>
    )
  }

  return (
    <Card className="p-6">
      <div className="mb-4">
        <h3 className="text-lg font-semibold">{title}</h3>
      </div>

      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart style={{ userSelect: "none" }}>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              labelLine={false}
              label={renderCustomizedLabel}
              outerRadius={110}
              innerRadius={70}
              fill="#8884d8"
              dataKey="value"
              stroke="hsl(var(--background))"
              strokeWidth={2}
            >
              {data.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={entry.color}
                  style={{ outline: "none" }}
                />
              ))}
            </Pie>
            <Tooltip
              content={
                <CustomTooltip
                  locale={locale}
                  currency={currency}
                  showOriginalCurrency={showOriginalCurrency}
                />
              }
            />
          </PieChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-4 space-y-2">
        {data.map((item, index) => (
          <div
            key={index}
            className="flex items-center justify-between text-sm"
          >
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <div
                className="w-3 h-3 rounded-full flex-shrink-0"
                style={{ backgroundColor: item.color }}
              />
              <span
                className="text-gray-700 dark:text-gray-300 truncate"
                title={item.name}
              >
                {item.name}
              </span>
            </div>
            <div className="text-right flex-shrink-0 ml-2">
              <div className="font-medium text-gray-900 dark:text-gray-100">
                {showOriginalCurrency &&
                item.currency &&
                item.currency !== currency
                  ? formatCurrency(item.value, locale, item.currency)
                  : formatCurrency(item.value, locale, currency)}
              </div>
              {showOriginalCurrency &&
                item.currency &&
                item.currency !== currency &&
                item.convertedValue && (
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    {formatCurrency(item.convertedValue, locale, currency)}
                  </div>
                )}
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}
