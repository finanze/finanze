import { useCallback, useEffect, useMemo, useState } from "react"
import { Button } from "@/components/ui/Button"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { formatCurrency } from "@/lib/formatters"
import { type ImportError, type ImportedData } from "@/types"
import { ProductType } from "@/types/position"
import { AlertTriangle, ChevronDown, ChevronUp, FileUp, X } from "lucide-react"

const PREVIEW_SAMPLE_LIMIT = 3
const REFERENCE_MAX_LENGTH = 50

const humanizeKey = (key: string) =>
  key
    .split("_")
    .filter(Boolean)
    .map(part =>
      part.length > 0 ? part[0].toUpperCase().concat(part.slice(1)) : "",
    )
    .join(" ")

const formatDetailValue = (fieldKey: string, value: string) => {
  if (value.length > REFERENCE_MAX_LENGTH) {
    return `${value.slice(0, REFERENCE_MAX_LENGTH - 3)}...`
  }
  return value
}

export interface ImportPreviewEntryDetail {
  key: string
  label: string
  value: string
}

export interface ImportPreviewSampleEntry {
  id: string
  label: string
  details: ImportPreviewEntryDetail[]
}

export interface ImportPreviewProductSummary {
  productType: ProductType
  count: number
  sampleEntries: ImportPreviewSampleEntry[]
  hiddenCount: number
}

export interface ImportPreviewPositionSummary {
  entityKey: string
  entityName: string
  products: ImportPreviewProductSummary[]
  totalCount: number
}

export interface ImportPreviewTransactionSummary {
  productType: ProductType
  count: number
  amounts: Record<string, number>
  sampleEntries: ImportPreviewSampleEntry[]
  hiddenCount: number
}

interface PreviewStrings {
  title: string
  description: string
  empty: string
  positionsTitle: string
  positionsSubtitle: string
  entityTotal: string
  productTotal: string
  transactionsTitle: string
  transactionsSubtitle: string
  transactionTotal: string
  showProductDetails: string
  hideProductDetails: string
  sampleEntriesLabel: string
  moreEntries: string
  cancel: string
  confirm: string
}

export type FileImportPreviewStrings = PreviewStrings

interface PreviewWarningStrings {
  title: string
  description: string
}

interface FileImportPreviewDialogProps {
  isOpen: boolean
  isLoading: boolean
  locale: string
  previewStrings: PreviewStrings
  loadingLabel: string
  productTypeLabels: Record<string, string>
  importData: ImportedData | null
  templateFieldLabels: Record<string, string>
  previewUnnamedEntry: string
  warningStrings: PreviewWarningStrings
  infoWarnings?: ImportError[] | null
  onClose: () => void
  onConfirm: () => void
}

export function FileImportPreviewDialog({
  isOpen,
  isLoading,
  locale,
  previewStrings,
  loadingLabel,
  productTypeLabels,
  importData,
  templateFieldLabels,
  previewUnnamedEntry,
  warningStrings,
  infoWarnings,
  onClose,
  onConfirm,
}: FileImportPreviewDialogProps) {
  if (!isOpen) {
    return null
  }

  const [expandedProducts, setExpandedProducts] = useState<
    Record<string, Partial<Record<ProductType, boolean>>>
  >({})

  useEffect(() => {
    if (!isOpen) {
      setExpandedProducts({})
    }
  }, [isOpen])

  const formatPreviewEntryLabel = useCallback(
    (entry: Record<string, any>) => {
      if (!entry || typeof entry !== "object") {
        return previewUnnamedEntry
      }

      const candidate =
        entry?.name ??
        entry?.target_name ??
        entry?.entity?.name ??
        entry?.description ??
        entry?.concept ??
        entry?.memo ??
        entry?.ticker ??
        entry?.symbol ??
        entry?.reference ??
        entry?.ref ??
        entry?.id

      if (typeof candidate === "string" && candidate.trim()) {
        return candidate.trim()
      }
      if (typeof candidate === "number") {
        return String(candidate)
      }
      return previewUnnamedEntry
    },
    [previewUnnamedEntry],
  )

  const buildPreviewEntryDetails = useCallback(
    (entry: Record<string, any>): ImportPreviewEntryDetail[] => {
      if (!entry || typeof entry !== "object") {
        return []
      }

      return Object.entries(entry)
        .map(([fieldKey, value]) => {
          if (value === null || value === undefined) {
            return null
          }
          const label = templateFieldLabels[fieldKey] ?? humanizeKey(fieldKey)
          if (typeof value === "string") {
            const trimmed = value.trim()
            if (!trimmed) {
              return null
            }
            return {
              key: fieldKey,
              label,
              value: formatDetailValue(fieldKey, trimmed),
            }
          }
          if (typeof value === "number") {
            if (!Number.isFinite(value)) {
              return null
            }
            return {
              key: fieldKey,
              label,
              value: String(value),
            }
          }
          if (typeof value === "boolean") {
            return {
              key: fieldKey,
              label,
              value: value ? "true" : "false",
            }
          }
          return null
        })
        .filter((detail): detail is ImportPreviewEntryDetail => Boolean(detail))
    },
    [templateFieldLabels],
  )

  const positionSummaries = useMemo<ImportPreviewPositionSummary[]>(() => {
    if (!importData?.positions) {
      return []
    }

    const positionsArray = Array.isArray(importData.positions)
      ? importData.positions
      : Object.values(importData.positions as Record<string, any>)

    return positionsArray
      .map((position, index) => {
        const products = position?.products ?? {}
        const productSummaries = Object.entries(products)
          .map(([rawType, value]) => {
            const rawEntries = (value as { entries?: any[] })?.entries
            const entries = Array.isArray(rawEntries) ? rawEntries : []
            if (entries.length === 0) {
              return null
            }

            const sampleEntries = entries
              .slice(0, PREVIEW_SAMPLE_LIMIT)
              .map((entry, entryIndex) => {
                const entryId =
                  entry?.id ??
                  entry?.tracker_key ??
                  entry?.reference ??
                  entry?.ticker ??
                  `${rawType}-${entryIndex}`
                return {
                  id: String(entryId),
                  label: formatPreviewEntryLabel(entry ?? {}),
                  details: buildPreviewEntryDetails(entry ?? {}),
                }
              })

            return {
              productType: rawType as ProductType,
              count: entries.length,
              sampleEntries,
              hiddenCount: Math.max(entries.length - sampleEntries.length, 0),
            }
          })
          .filter((summary): summary is ImportPreviewProductSummary =>
            Boolean(summary),
          )

        const totalCount = productSummaries.reduce(
          (sum, item) => sum + item.count,
          0,
        )
        if (totalCount === 0) {
          return null
        }

        return {
          entityKey:
            position?.entity?.id || position?.id || `preview-entity-${index}`,
          entityName:
            position?.entity?.name ||
            position?.entity?.id ||
            position?.id ||
            "—",
          products: productSummaries,
          totalCount,
        }
      })
      .filter((summary): summary is ImportPreviewPositionSummary =>
        Boolean(summary),
      )
  }, [importData, formatPreviewEntryLabel, buildPreviewEntryDetails])

  const transactionSummaries = useMemo<
    ImportPreviewTransactionSummary[]
  >(() => {
    if (!importData?.transactions) {
      return []
    }

    type AggregateInfo = {
      count: number
      amounts: Record<string, number>
      sampleEntries: ImportPreviewSampleEntry[]
    }

    const aggregate = new Map<ProductType, AggregateInfo>()

    const collect = (transactions?: any) => {
      if (!transactions) return
      const list = Array.isArray(transactions)
        ? transactions
        : Object.values(transactions as Record<string, any>)
      list.forEach((tx: Record<string, any>, idx: number) => {
        const productType =
          (tx?.product_type as ProductType) || ProductType.ACCOUNT
        const current = aggregate.get(productType) ?? {
          count: 0,
          amounts: {},
          sampleEntries: [],
        }

        current.count += 1

        const currency = typeof tx?.currency === "string" ? tx.currency : null
        const amountValue =
          typeof tx?.amount === "number" && Number.isFinite(tx.amount)
            ? tx.amount
            : null
        if (currency && amountValue !== null) {
          current.amounts[currency] =
            (current.amounts[currency] ?? 0) + amountValue
        }

        if (current.sampleEntries.length < PREVIEW_SAMPLE_LIMIT) {
          const entryIndex = current.sampleEntries.length
          const entryId =
            tx?.id ??
            tx?.tracker_key ??
            tx?.reference ??
            tx?.ticker ??
            `${productType}-${idx}-${entryIndex}`
          current.sampleEntries.push({
            id: String(entryId),
            label: formatPreviewEntryLabel(tx ?? {}),
            details: buildPreviewEntryDetails(tx ?? {}),
          })
        }

        aggregate.set(productType, current)
      })
    }

    collect(importData.transactions.account)
    collect(importData.transactions.investment)

    return Array.from(aggregate.entries()).map(([productType, info]) => ({
      productType,
      count: info.count,
      amounts: info.amounts,
      sampleEntries: info.sampleEntries,
      hiddenCount: Math.max(info.count - info.sampleEntries.length, 0),
    }))
  }, [importData, formatPreviewEntryLabel, buildPreviewEntryDetails])

  const toggleProductDetails = useCallback(
    (entityKey: string, productType: ProductType) => {
      setExpandedProducts(prev => {
        const entityState = prev[entityKey] ?? {}
        return {
          ...prev,
          [entityKey]: {
            ...entityState,
            [productType]: !entityState[productType],
          },
        }
      })
    },
    [],
  )

  const hasPositions = positionSummaries.length > 0
  const hasTransactions = transactionSummaries.length > 0
  const hasData = hasPositions || hasTransactions
  const hasWarnings = Boolean(infoWarnings && infoWarnings.length > 0)

  return (
    <div className="fixed inset-0 z-[11000] flex items-center justify-center bg-black/60 p-1 sm:p-3 lg:p-6">
      <Card className="flex max-h-[90vh] w-full max-w-3xl flex-col">
        <CardHeader className="space-y-1">
          <CardTitle className="text-lg font-semibold">
            {previewStrings.title}
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            {previewStrings.description}
          </p>
        </CardHeader>
        <CardContent className="flex-1 space-y-4 overflow-y-auto px-3 py-3 sm:space-y-6 sm:px-6 sm:py-5">
          {hasWarnings ? (
            <div className="rounded-md border border-border/60 bg-muted/40 p-3 text-sm text-muted-foreground dark:border-white/15 dark:bg-white/5">
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 text-muted-foreground" />
                <div className="space-y-2">
                  <p className="font-medium text-foreground">
                    {warningStrings.title}
                  </p>
                  {infoWarnings?.map((warning, index) => {
                    const columns = Array.isArray(warning.detail)
                      ? warning.detail.filter(
                          (value): value is string => typeof value === "string",
                        )
                      : []
                    return (
                      <div
                        key={`${warning.entry}-${index}`}
                        className="space-y-1"
                      >
                        <p className="text-xs text-muted-foreground">
                          {warningStrings.description.replace(
                            "{entry}",
                            warning.entry,
                          )}
                        </p>
                        {columns.length > 0 ? (
                          <ul className="list-disc list-inside text-xs text-muted-foreground">
                            {columns.map((column, columnIndex) => (
                              <li key={`${warning.entry}-${columnIndex}`}>
                                {column}
                              </li>
                            ))}
                          </ul>
                        ) : null}
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          ) : null}
          {!hasData ? (
            <div className="py-10 text-center text-sm text-muted-foreground">
              {previewStrings.empty}
            </div>
          ) : (
            <div className="space-y-6">
              {hasPositions ? (
                <section className="space-y-3">
                  <div>
                    <h3 className="text-sm font-semibold">
                      {previewStrings.positionsTitle}
                    </h3>
                    <p className="text-xs text-muted-foreground">
                      {previewStrings.positionsSubtitle}
                    </p>
                  </div>
                  <div className="space-y-3">
                    {positionSummaries.map(summary => (
                      <div
                        key={summary.entityKey}
                        className="rounded-lg border border-border/60 bg-muted/20 p-3 sm:p-4"
                      >
                        <div className="flex flex-wrap items-baseline justify-between gap-2">
                          <div className="font-medium text-foreground">
                            {summary.entityName}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {previewStrings.entityTotal.replace(
                              "{count}",
                              summary.totalCount.toString(),
                            )}
                          </div>
                        </div>
                        <div className="mt-3 space-y-2">
                          {summary.products.map(product => {
                            const isExpanded = Boolean(
                              expandedProducts[summary.entityKey]?.[
                                product.productType
                              ],
                            )
                            return (
                              <div
                                key={`${summary.entityKey}-${product.productType}`}
                                className="rounded-md border border-border/50 bg-background/50"
                              >
                                <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
                                  <div>
                                    <p className="text-sm font-medium text-foreground">
                                      {productTypeLabels[product.productType] ??
                                        product.productType}
                                    </p>
                                    <p className="text-xs text-muted-foreground">
                                      {previewStrings.productTotal.replace(
                                        "{count}",
                                        product.count.toString(),
                                      )}
                                    </p>
                                  </div>
                                  <Button
                                    type="button"
                                    variant="ghost"
                                    size="sm"
                                    className="h-8 px-2 text-xs"
                                    onClick={() =>
                                      toggleProductDetails(
                                        summary.entityKey,
                                        product.productType,
                                      )
                                    }
                                  >
                                    {isExpanded ? (
                                      <>
                                        <ChevronUp className="mr-1 h-3.5 w-3.5" />
                                        {previewStrings.hideProductDetails}
                                      </>
                                    ) : (
                                      <>
                                        <ChevronDown className="mr-1 h-3.5 w-3.5" />
                                        {previewStrings.showProductDetails}
                                      </>
                                    )}
                                  </Button>
                                </div>
                                {isExpanded ? (
                                  <div className="space-y-2 border-t border-border/40 px-3 py-2">
                                    <p className="text-xs font-medium text-muted-foreground">
                                      {previewStrings.sampleEntriesLabel}
                                    </p>
                                    <ul className="space-y-1 text-xs">
                                      {product.sampleEntries.map(entry => (
                                        <li
                                          key={`${summary.entityKey}-${product.productType}-${entry.id}`}
                                          className="rounded bg-muted/40 px-2 py-1 text-foreground dark:bg-muted/30"
                                        >
                                          <div className="text-sm font-medium text-foreground">
                                            {entry.label}
                                          </div>
                                          {entry.details.length > 0 ? (
                                            <dl className="mt-1 flex flex-wrap gap-2 text-[11px] text-muted-foreground">
                                              {entry.details.map(detail => (
                                                <div
                                                  key={`${entry.id}-${detail.key}`}
                                                  className="rounded bg-background/80 px-2 py-0.5 dark:bg-background/20"
                                                >
                                                  <dt className="font-medium text-foreground">
                                                    {detail.label}
                                                  </dt>
                                                  <dd>{detail.value}</dd>
                                                </div>
                                              ))}
                                            </dl>
                                          ) : null}
                                        </li>
                                      ))}
                                    </ul>
                                    {product.hiddenCount > 0 ? (
                                      <p className="text-xs text-muted-foreground">
                                        {previewStrings.moreEntries.replace(
                                          "{count}",
                                          product.hiddenCount.toString(),
                                        )}
                                      </p>
                                    ) : null}
                                  </div>
                                ) : null}
                              </div>
                            )
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              ) : null}

              {hasTransactions ? (
                <section className="space-y-3">
                  <div>
                    <h3 className="text-sm font-semibold">
                      {previewStrings.transactionsTitle}
                    </h3>
                    <p className="text-xs text-muted-foreground">
                      {previewStrings.transactionsSubtitle}
                    </p>
                  </div>
                  <div className="grid gap-3 grid-cols-[repeat(auto-fit,minmax(280px,1fr))]">
                    {transactionSummaries.map(item => {
                      const amounts = Object.entries(item.amounts).map(
                        ([currency, amount]) => ({
                          currency,
                          formatted: formatCurrency(amount, locale, currency),
                        }),
                      )
                      return (
                        <div
                          key={item.productType}
                          className="rounded-lg border border-border/60 bg-muted/15 p-3"
                        >
                          <div className="font-medium text-foreground">
                            {productTypeLabels[item.productType] ??
                              item.productType}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {previewStrings.transactionTotal.replace(
                              "{count}",
                              item.count.toString(),
                            )}
                          </div>
                          {amounts.length > 0 ? (
                            <div className="mt-2 flex flex-wrap gap-1.5">
                              {amounts.map(amountInfo => (
                                <span
                                  key={`${item.productType}-${amountInfo.currency}`}
                                  className="rounded-md bg-background/80 px-2 py-0.5 text-xs text-muted-foreground dark:bg-muted/40"
                                >
                                  {amountInfo.formatted}
                                </span>
                              ))}
                            </div>
                          ) : null}
                          {item.sampleEntries.length > 0 ? (
                            <div className="mt-3 space-y-2 border-t border-border/40 pt-2">
                              <p className="text-xs font-medium text-muted-foreground">
                                {previewStrings.sampleEntriesLabel}
                              </p>
                              <ul className="space-y-1 text-xs">
                                {item.sampleEntries.map(entry => (
                                  <li
                                    key={`${item.productType}-${entry.id}`}
                                    className="rounded bg-muted/40 px-2 py-1 text-foreground dark:bg-muted/30"
                                  >
                                    <div className="text-sm font-medium text-foreground">
                                      {entry.label}
                                    </div>
                                    {entry.details.length > 0 ? (
                                      <dl className="mt-1 flex flex-wrap gap-2 text-[11px] text-muted-foreground">
                                        {entry.details.map(detail => (
                                          <div
                                            key={`${entry.id}-${detail.key}`}
                                            className="rounded bg-background/80 px-2 py-0.5 dark:bg-background/20"
                                          >
                                            <dt className="font-medium text-foreground">
                                              {detail.label}
                                            </dt>
                                            <dd>{detail.value}</dd>
                                          </div>
                                        ))}
                                      </dl>
                                    ) : null}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          ) : null}
                          {item.hiddenCount > 0 ? (
                            <p className="mt-2 text-xs text-muted-foreground">
                              {previewStrings.moreEntries.replace(
                                "{count}",
                                item.hiddenCount.toString(),
                              )}
                            </p>
                          ) : null}
                        </div>
                      )
                    })}
                  </div>
                </section>
              ) : null}
            </div>
          )}
        </CardContent>
        <CardFooter className="flex flex-wrap items-center justify-end gap-2 border-t border-border/60 px-3 py-3 sm:px-6 sm:py-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            disabled={isLoading}
            className="inline-flex items-center gap-2"
          >
            <X className="h-4 w-4" />
            {previewStrings.cancel}
          </Button>
          <Button
            size="sm"
            onClick={onConfirm}
            disabled={isLoading}
            className="inline-flex items-center gap-2"
          >
            {isLoading ? (
              <LoadingSpinner className="mr-2 h-4 w-4" />
            ) : (
              <FileUp className="mr-2 h-4 w-4" />
            )}
            {isLoading ? loadingLabel : previewStrings.confirm}
          </Button>
        </CardFooter>
      </Card>
    </div>
  )
}
