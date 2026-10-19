import { useCallback, useEffect, useState } from "react"
import { motion } from "framer-motion"
import { AlertTriangle, Bot, Check, Copy, Info, RefreshCw } from "lucide-react"
import { useI18n } from "@/i18n"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card"
import { Switch } from "@/components/ui/Switch"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { SecretInput } from "@/components/ui/SecretInput"
import { Label } from "@/components/ui/Label"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { ConfirmationDialog } from "@/components/ui/ConfirmationDialog"
import { useAppContext } from "@/context/AppContext"
import { copyToClipboard } from "@/lib/clipboard"
import {
  getApiServerInfo,
  getMcpConfig,
  regenerateMcpToken,
  updateMcpConfig,
} from "@/services/api"
import type { McpConfig } from "@/types/mcp"

type McpClient = "vscode" | "claudeCode" | "cursor" | "claudeDesktop"

const MCP_CLIENTS: McpClient[] = [
  "vscode",
  "claudeCode",
  "cursor",
  "claudeDesktop",
]
const TOKEN_MASK = "••••••••••••"
const LOCAL_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
const CARD_CLASS =
  "-mx-6 md:mx-0 rounded-none md:rounded-lg border-x-0 md:border-x"

function buildSnippet(client: McpClient, url: string, token: string): string {
  const authorization = `Bearer ${token}`
  switch (client) {
    case "vscode":
      return JSON.stringify(
        {
          servers: {
            finanze: {
              type: "http",
              url,
              headers: { Authorization: authorization },
            },
          },
        },
        null,
        2,
      )
    case "claudeCode":
      return `claude mcp add --transport http finanze ${url} --header "Authorization: ${authorization}"`
    case "cursor":
      return JSON.stringify(
        {
          mcpServers: {
            finanze: { url, headers: { Authorization: authorization } },
          },
        },
        null,
        2,
      )
    case "claudeDesktop": {
      const { protocol, hostname } = new URL(url)
      const args = [
        "-y",
        "mcp-remote",
        url,
        "--header",
        "Authorization:${AUTH_HEADER}",
      ]
      if (protocol === "http:" && !LOCAL_HOSTS.includes(hostname)) {
        args.push("--allow-http")
      }
      return JSON.stringify(
        {
          mcpServers: {
            finanze: {
              command: "npx",
              args,
              env: { AUTH_HEADER: authorization },
            },
          },
        },
        null,
        2,
      )
    }
  }
}

export function McpTab() {
  const { t } = useI18n()
  const { showToast } = useAppContext()
  const [config, setConfig] = useState<McpConfig | null>(null)
  const [serverUrl, setServerUrl] = useState("")
  const [isSaving, setIsSaving] = useState(false)
  const [isRegenerating, setIsRegenerating] = useState(false)
  const [showRegenerateConfirm, setShowRegenerateConfirm] = useState(false)
  const [client, setClient] = useState<McpClient>("vscode")
  const [copied, setCopied] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([getMcpConfig(), getApiServerInfo()])
      .then(([mcpConfig, serverInfo]) => {
        setConfig(mcpConfig)
        setServerUrl(
          new URL(
            `${serverInfo.baseUrl}/mcp`,
            window.location.origin,
          ).toString(),
        )
      })
      .catch(() => showToast(t.settings.mcp.loadError, "error"))
  }, [])

  const update = useCallback(
    async (enabled: boolean, readOnly: boolean) => {
      setIsSaving(true)
      try {
        setConfig(await updateMcpConfig({ enabled, read_only: readOnly }))
      } catch {
        showToast(t.settings.mcp.updateError, "error")
      } finally {
        setIsSaving(false)
      }
    },
    [showToast, t],
  )

  const handleRegenerate = async () => {
    setIsRegenerating(true)
    try {
      setConfig(await regenerateMcpToken())
      showToast(t.settings.mcp.tokenRegenerated, "success")
    } catch {
      showToast(t.settings.mcp.regenerateError, "error")
    } finally {
      setIsRegenerating(false)
      setShowRegenerateConfirm(false)
    }
  }

  const handleCopy = async (key: string, text: string) => {
    if (await copyToClipboard(text)) {
      setCopied(key)
      setTimeout(() => setCopied(prev => (prev === key ? null : prev)), 1500)
    }
  }

  const copyButton = (key: string, text: string) => (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      className="shrink-0"
      data-testid={`mcp-copy-${key}`}
      aria-label={copied === key ? t.common.copied : t.common.copy}
      onClick={() => handleCopy(key, text)}
    >
      {copied === key ? (
        <Check className="h-4 w-4 text-emerald-500" />
      ) : (
        <Copy className="h-4 w-4" />
      )}
    </Button>
  )

  if (!config) {
    return (
      <div className="flex justify-center py-12">
        <LoadingSpinner />
      </div>
    )
  }

  const token = config.token ?? ""
  const showConnection = config.enabled && !!token

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="space-y-4"
    >
      <Card className={CARD_CLASS}>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-primary" />
            <CardTitle>{t.settings.mcp.title}</CardTitle>
          </div>
          <CardDescription>{t.settings.mcp.description}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between gap-4">
            <div className="space-y-1">
              <p className="text-sm font-medium">
                {t.settings.mcp.enableLabel}
              </p>
              <p className="text-xs text-muted-foreground">
                {t.settings.mcp.enableDescription}
              </p>
            </div>
            <Switch
              data-testid="mcp-enabled"
              checked={config.enabled}
              disabled={isSaving}
              onCheckedChange={checked => update(checked, config.read_only)}
            />
          </div>
          <div className="flex items-center justify-between gap-4">
            <div className="space-y-1">
              <p className="text-sm font-medium">
                {t.settings.mcp.readOnlyLabel}
              </p>
              <p className="text-xs text-muted-foreground">
                {t.settings.mcp.readOnlyDescription}
              </p>
            </div>
            <Switch
              data-testid="mcp-read-only"
              checked={config.read_only}
              disabled={isSaving || !config.enabled}
              onCheckedChange={checked => update(config.enabled, checked)}
            />
          </div>
          {config.enabled && !config.read_only && (
            <div className="flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-700 dark:text-amber-400">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <span>{t.settings.mcp.readOnlyWarning}</span>
            </div>
          )}
        </CardContent>
      </Card>

      {showConnection && (
        <Card className={CARD_CLASS}>
          <CardHeader>
            <CardTitle>{t.settings.mcp.connectionTitle}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="mcp-server-url">{t.settings.mcp.serverUrl}</Label>
              <div className="flex gap-2">
                <Input
                  id="mcp-server-url"
                  data-testid="mcp-server-url"
                  value={serverUrl}
                  readOnly
                  className="font-mono text-xs"
                />
                {copyButton("url", serverUrl)}
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="mcp-token">{t.settings.mcp.token}</Label>
              <div className="flex gap-2">
                <div className="flex-1">
                  <SecretInput
                    id="mcp-token"
                    data-testid="mcp-token"
                    value={token}
                    readOnly
                    className="font-mono text-xs"
                  />
                </div>
                {copyButton("token", token)}
                <Button
                  type="button"
                  variant="outline"
                  data-testid="mcp-regenerate-token"
                  disabled={isRegenerating}
                  onClick={() => setShowRegenerateConfirm(true)}
                >
                  <RefreshCw className="mr-2 h-4 w-4" />
                  {t.settings.mcp.regenerateToken}
                </Button>
              </div>
            </div>
            <div className="flex items-start gap-2 text-xs text-muted-foreground">
              <Info className="h-4 w-4 shrink-0" />
              <span>{t.settings.mcp.runningNote}</span>
            </div>
          </CardContent>
        </Card>
      )}

      {showConnection && (
        <Card className={CARD_CLASS}>
          <CardHeader>
            <CardTitle>{t.settings.mcp.clientsTitle}</CardTitle>
            <CardDescription>
              {t.settings.mcp.clientsDescription}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-wrap gap-2">
              {MCP_CLIENTS.map(option => (
                <Button
                  key={option}
                  type="button"
                  size="sm"
                  variant={option === client ? "default" : "outline"}
                  onClick={() => setClient(option)}
                >
                  {t.settings.mcp.clients[option]}
                </Button>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">
              {t.settings.mcp.clientHints[client]}
            </p>
            <div className="relative">
              <pre
                data-testid="mcp-snippet"
                className="overflow-x-auto rounded-md bg-muted p-3 pr-14 font-mono text-xs"
              >
                {buildSnippet(client, serverUrl, TOKEN_MASK)}
              </pre>
              <div
                className={
                  client === "claudeCode"
                    ? "absolute right-2 top-1/2 -translate-y-1/2"
                    : "absolute right-2 top-2"
                }
              >
                {copyButton("snippet", buildSnippet(client, serverUrl, token))}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <ConfirmationDialog
        isOpen={showRegenerateConfirm}
        title={t.settings.mcp.regenerateConfirmTitle}
        message={t.settings.mcp.regenerateConfirmMessage}
        confirmText={t.settings.mcp.regenerateToken}
        cancelText={t.common.cancel}
        onConfirm={handleRegenerate}
        onCancel={() => setShowRegenerateConfirm(false)}
        isLoading={isRegenerating}
      />
    </motion.div>
  )
}
