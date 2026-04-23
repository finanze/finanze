import { useState, useEffect, useCallback, useRef } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { createPortal } from "react-dom"
import { useI18n } from "@/i18n"
import { useModalBackHandler } from "@/hooks/useModalBackHandler"
import { getCryptoWalletAddresses } from "@/services/api"
import { copyToClipboard } from "@/lib/clipboard"
import { Button } from "@/components/ui/Button"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { X, Eye, EyeOff, Copy, Check, Key } from "lucide-react"
import { Sensitive } from "@/components/ui/Sensitive"
import type { WalletAddressesResponse, DerivedAddress } from "@/types"

interface WalletAddressesDialogProps {
  isOpen: boolean
  onClose: () => void
  walletId: string | null
  walletName: string
}

const obfuscateAddress = (address: string): string => {
  if (address.length <= 12) return address
  return `${address.slice(0, 6)}${"•".repeat(6)}${address.slice(-4)}`
}

const COIN_SYMBOLS: Record<string, string> = {
  BITCOIN: "BTC",
  LITECOIN: "LTC",
}

const formatBalance = (balance: number, coinType: string): string => {
  const symbol = COIN_SYMBOLS[coinType] ?? coinType
  if (balance === 0) return `0 ${symbol}`
  return `${balance} ${symbol}`
}

function AddressRow({
  addr,
  revealed,
  copiedAddress,
  onCopy,
  coinType,
}: {
  addr: DerivedAddress
  revealed: boolean
  copiedAddress: string | null
  onCopy: (address: string) => void
  coinType: string
}) {
  const display = revealed ? addr.address : obfuscateAddress(addr.address)
  const isCopied = copiedAddress === addr.address
  const hasBalance = addr.balance > 0

  const handleRowClick = () => {
    if (revealed) onCopy(addr.address)
  }

  return (
    <div
      className={`text-xs py-1.5 px-2 rounded group/row transition-colors duration-150 ${
        isCopied
          ? "bg-green-50 dark:bg-green-900/20 ring-1 ring-green-200 dark:ring-green-800"
          : "bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700/70"
      } ${revealed ? "cursor-pointer active:scale-[0.995]" : ""}`}
      onClick={handleRowClick}
      role={revealed ? "button" : undefined}
      tabIndex={revealed ? 0 : undefined}
      onKeyDown={e => {
        if (revealed && (e.key === "Enter" || e.key === " ")) {
          e.preventDefault()
          onCopy(addr.address)
        }
      }}
    >
      <div className="flex items-center gap-2 sm:hidden">
        <span className="text-muted-foreground font-mono w-8 flex-shrink-0">
          {addr.index}
        </span>
        <span className="font-mono text-muted-foreground truncate">
          {addr.path}
        </span>
        <span className="ml-auto flex-shrink-0">
          {isCopied ? (
            <Check className="h-3 w-3 text-green-600 dark:text-green-400" />
          ) : revealed ? (
            <Copy className="h-3 w-3 text-muted-foreground opacity-50" />
          ) : null}
        </span>
      </div>
      <div className="mt-0.5 sm:hidden flex items-center gap-2">
        <span
          className={`font-mono flex-1 ${revealed ? "break-all" : "tracking-wider"}`}
        >
          {display}
        </span>
        {hasBalance && (
          <Sensitive>
            <span className="font-mono text-amber-600 dark:text-amber-400 flex-shrink-0 text-[11px]">
              {formatBalance(addr.balance, coinType)}
            </span>
          </Sensitive>
        )}
      </div>

      <div className="hidden sm:flex items-center gap-2">
        <span className="text-muted-foreground font-mono w-10 flex-shrink-0">
          {addr.index}
        </span>
        <span className="font-mono text-muted-foreground flex-shrink-0">
          {addr.path}
        </span>
        <span
          className={`font-mono flex-1 text-right ${revealed ? "break-all" : "tracking-wider"}`}
        >
          {display}
        </span>
        {hasBalance && (
          <Sensitive>
            <span className="font-mono text-amber-600 dark:text-amber-400 flex-shrink-0 text-[11px] w-28 text-right">
              {formatBalance(addr.balance, coinType)}
            </span>
          </Sensitive>
        )}
        <span className="flex-shrink-0 w-4">
          {isCopied ? (
            <Check className="h-3 w-3 text-green-600 dark:text-green-400" />
          ) : revealed ? (
            <Copy className="h-3 w-3 text-muted-foreground opacity-0 group-hover/row:opacity-50 transition-opacity duration-150" />
          ) : null}
        </span>
      </div>
    </div>
  )
}

export function WalletAddressesDialog({
  isOpen,
  onClose,
  walletId,
  walletName,
}: WalletAddressesDialogProps) {
  const { t } = useI18n()
  const [data, setData] = useState<WalletAddressesResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [revealed, setRevealed] = useState(false)
  const [copiedAddress, setCopiedAddress] = useState<string | null>(null)
  const copyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useModalBackHandler(isOpen, onClose)

  useEffect(() => {
    if (!isOpen || !walletId) {
      setData(null)
      setError(null)
      setRevealed(false)
      setCopiedAddress(null)
      return
    }

    let cancelled = false
    setIsLoading(true)
    setError(null)

    getCryptoWalletAddresses(walletId)
      .then(result => {
        if (!cancelled) setData(result)
      })
      .catch(() => {
        if (!cancelled)
          setError(
            (t.walletManagement as Record<string, string>).addressesError ??
              "Failed to load addresses.",
          )
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [isOpen, walletId, t.walletManagement])

  useEffect(() => {
    return () => {
      if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current)
    }
  }, [])

  const handleCopy = useCallback((address: string) => {
    const performCopy = async () => {
      const ok = await copyToClipboard(address)
      if (!ok) return
      setCopiedAddress(address)
      if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current)
      copyTimeoutRef.current = setTimeout(() => {
        setCopiedAddress(prev => (prev === address ? null : prev))
      }, 1500)
    }
    void performCopy()
  }, [])

  const wm = t.walletManagement as Record<string, string>
  const receiving = data?.hd_wallet?.receiving ?? []
  const change = data?.hd_wallet?.change ?? []
  const hasAddresses = receiving.length > 0 || change.length > 0

  const dialogContent = (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-[18000]"
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="w-full max-w-2xl mx-auto max-h-[85vh] flex flex-col"
            onClick={e => e.stopPropagation()}
          >
            <Card className="w-full flex flex-col overflow-hidden">
              <CardHeader className="flex flex-row items-center justify-between gap-2 pb-3 flex-shrink-0">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="p-1.5 rounded-lg bg-amber-100 dark:bg-amber-900/30 flex-shrink-0">
                    <Key className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                  </div>
                  <div className="min-w-0">
                    <CardTitle className="text-base sm:text-lg truncate">
                      {walletName}
                    </CardTitle>
                    {data?.hd_wallet?.xpub && (
                      <p className="text-xs text-muted-foreground font-mono truncate">
                        {data.hd_wallet.xpub.slice(0, 12)}...
                        {data.hd_wallet.xpub.slice(-6)}
                      </p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1 flex-shrink-0">
                  {hasAddresses && !isLoading && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 w-8 p-0"
                      onClick={() => setRevealed(prev => !prev)}
                      title={revealed ? wm.hideAddresses : wm.showAddresses}
                    >
                      {revealed ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 w-8 p-0"
                    onClick={onClose}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="overflow-y-auto min-h-0 pb-4">
                {isLoading && (
                  <div className="flex flex-col items-center justify-center py-12">
                    <LoadingSpinner size="lg" />
                    <p className="mt-4 text-sm text-muted-foreground">
                      {t.common.loading}
                    </p>
                  </div>
                )}

                {error && (
                  <div className="text-center py-8">
                    <p className="text-sm text-destructive">{error}</p>
                    <Button
                      variant="outline"
                      size="sm"
                      className="mt-3"
                      onClick={() => {
                        if (walletId) {
                          setIsLoading(true)
                          setError(null)
                          getCryptoWalletAddresses(walletId)
                            .then(setData)
                            .catch(() => setError(wm.addressesError))
                            .finally(() => setIsLoading(false))
                        }
                      }}
                    >
                      {t.common.retry}
                    </Button>
                  </div>
                )}

                {!isLoading && !error && !hasAddresses && (
                  <div className="text-center py-8">
                    <p className="text-sm text-muted-foreground">
                      {wm.noAddresses}
                    </p>
                  </div>
                )}

                {!isLoading && !error && hasAddresses && (
                  <div className="space-y-4">
                    {receiving.length > 0 && (
                      <div className="space-y-1.5">
                        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                          {wm.receivingAddresses}
                        </p>
                        <div className="space-y-1">
                          {receiving.map(addr => (
                            <AddressRow
                              key={addr.path}
                              addr={addr}
                              revealed={revealed}
                              copiedAddress={copiedAddress}
                              onCopy={handleCopy}
                              coinType={data?.hd_wallet?.coin_type ?? ""}
                            />
                          ))}
                        </div>
                      </div>
                    )}

                    {change.length > 0 && (
                      <div className="space-y-1.5">
                        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                          {wm.changeAddresses}
                        </p>
                        <div className="space-y-1">
                          {change.map(addr => (
                            <AddressRow
                              key={addr.path}
                              addr={addr}
                              revealed={revealed}
                              copiedAddress={copiedAddress}
                              onCopy={handleCopy}
                              coinType={data?.hd_wallet?.coin_type ?? ""}
                            />
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )

  if (typeof document === "undefined") return null
  return createPortal(dialogContent, document.body)
}
