import { useState, useEffect, useCallback } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { useAppContext } from "@/context/AppContext"
import { useEntityWorkflow } from "@/context/EntityWorkflowContext"
import { useI18n } from "@/i18n"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { Card } from "@/components/ui/Card"
import { AdaptiveLogo } from "@/components/ui/AdaptiveLogo"
import { ConfirmationDialog } from "@/components/ui/ConfirmationDialog"
import { Search, Landmark, Check } from "lucide-react"
import {
  ExternalEntityConnectionResult,
  ExternalEntitySetupResponseCode,
  ExternalIntegrationType,
  ExternalIntegrationStatus,
} from "@/types"
import {
  getExternalEntityCandidates,
  connectExternalEntity,
  completeExternalEntityConnection,
  getImageUrl,
  disconnectExternalEntity,
} from "@/services/api"
import { AVAILABLE_COUNTRIES, getCountryFlag } from "@/constants/countries"
import { isNativeMobile, isWeb } from "@/lib/platform"
import { openInAppBrowser, closeInAppBrowser } from "@/lib/mobile"
import { useModalBackHandler } from "@/hooks/useModalBackHandler"

export const ENABLE_BANKING_PROVIDER = "ENABLE_BANKING"

function buildWebCompletionUrl(): string | undefined {
  if (!isWeb()) return undefined
  return `${window.location.origin}${window.location.pathname}#/entities`
}

async function openExternalAuthLink(link: string) {
  if (isNativeMobile()) {
    try {
      await openInAppBrowser(link)
    } catch {
      // ignore in-app browser open errors
    }
    return
  }
  if (isWeb()) {
    // Web/Docker: navigate the same tab; the provider page redirects back
    // to this app with the code/state once the authorization completes.
    window.location.assign(link)
    return
  }
  try {
    window.open(link, "_blank")
  } catch {
    // ignore window open errors
  }
}

async function closeExternalAuthBrowser() {
  try {
    await closeInAppBrowser()
  } catch {
    // ignore in-app browser close errors
  }
}

interface ExternalCandidate {
  id: string
  name: string
  bic: string
  icon?: string | null
}

export function useExternalEntityConnection() {
  const {
    fetchEntities,
    showToast,
    externalIntegrations,
    fetchExternalIntegrations,
  } = useAppContext()
  const { setView } = useEntityWorkflow()
  const { t } = useI18n()

  const [showAddExternalEntity, setShowAddExternalEntity] = useState(false)
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null)
  const [selectedCountry, setSelectedCountry] = useState<string | null>(null)
  const [candidatesLoading, setCandidatesLoading] = useState(false)
  const [candidatesError, setCandidatesError] = useState<string | null>(null)
  const [externalCandidates, setExternalCandidates] = useState<
    ExternalCandidate[]
  >([])
  const [connectingInstitutionId, setConnectingInstitutionId] = useState<
    string | null
  >(null)
  const [showCompleteExternalModal, setShowCompleteExternalModal] =
    useState(false)
  const [externalLink, setExternalLink] = useState<string | null>(null)
  // External entity id returned by connect endpoint (used to complete)
  const [externalEntityId, setExternalEntityId] = useState<string | null>(null)
  // Provider of the pending completion (used to tailor the modal actions)
  const [externalCompleteProvider, setExternalCompleteProvider] = useState<
    string | null
  >(null)
  const [completingConnection, setCompletingConnection] = useState(false)
  const [alreadyLinked, setAlreadyLinked] = useState(false)
  const [candidateIcons, setCandidateIcons] = useState<Record<string, string>>(
    {},
  )
  const [institutionSearch, setInstitutionSearch] = useState("")
  const [ebConfirmInstitutionId, setEbConfirmInstitutionId] = useState<
    string | null
  >(null)
  // Linking existing externally provided entity
  const [linkingExternalEntityId, setLinkingExternalEntityId] = useState<
    string | null
  >(null)

  useModalBackHandler(showAddExternalEntity, () =>
    setShowAddExternalEntity(false),
  )
  useModalBackHandler(showCompleteExternalModal, () =>
    setShowCompleteExternalModal(false),
  )

  useEffect(() => {
    fetchExternalIntegrations()
  }, [fetchExternalIntegrations])

  const enabledEntityProviders = externalIntegrations.filter(
    integ =>
      integ.type === ExternalIntegrationType.ENTITY_PROVIDER &&
      integ.status === ExternalIntegrationStatus.ON &&
      integ.available,
  )

  const hasProviderIntegration = enabledEntityProviders.length > 0

  const hasAvailableEntityProvider = externalIntegrations.some(
    integ =>
      integ.type === ExternalIntegrationType.ENTITY_PROVIDER && integ.available,
  )

  const openAddExternalEntity = () => {
    setShowAddExternalEntity(true)
    // Reset state
    setSelectedProvider(
      enabledEntityProviders.length === 1 ? enabledEntityProviders[0].id : null,
    )
    setSelectedCountry(null)
    setExternalCandidates([])
    setCandidatesError(null)
    setInstitutionSearch("")
    setAlreadyLinked(false)
  }

  const closeAddExternalEntity = () => {
    setShowAddExternalEntity(false)
    setEbConfirmInstitutionId(null)
  }

  const handleSelectProvider = (providerId: string) => {
    setSelectedProvider(providerId)
    setSelectedCountry(null)
    setExternalCandidates([])
    setCandidatesError(null)
    setInstitutionSearch("")
    setAlreadyLinked(false)
  }

  const fetchCandidates = async (country: string) => {
    setSelectedCountry(country)
    setCandidatesLoading(true)
    setCandidatesError(null)
    setExternalCandidates([])
    setInstitutionSearch("")
    try {
      const res = await getExternalEntityCandidates(country, selectedProvider)
      const sorted = [...(res.entities || [])].sort((a, b) =>
        a.name.localeCompare(b.name),
      )
      setExternalCandidates(sorted)
    } catch (e: any) {
      setCandidatesError(e?.message || "error")
    } finally {
      setCandidatesLoading(false)
    }
  }

  const handleChangeCountry = () => {
    setSelectedCountry(null)
    setExternalCandidates([])
    setCandidatesError(null)
    setInstitutionSearch("")
  }

  const handleConnectExternalEntity = async (institutionId: string) => {
    setConnectingInstitutionId(institutionId)
    setAlreadyLinked(false)
    try {
      const result: ExternalEntityConnectionResult =
        await connectExternalEntity({
          institution_id: institutionId,
          provider: selectedProvider,
          completion_url: buildWebCompletionUrl(),
        })
      if (result.code === ExternalEntitySetupResponseCode.ALREADY_LINKED) {
        setAlreadyLinked(true)
        await fetchEntities()
      } else if (
        result.code === ExternalEntitySetupResponseCode.CONTINUE_WITH_LINK &&
        result.link &&
        result.id
      ) {
        setExternalEntityId(result.id)
        setExternalCompleteProvider(selectedProvider)
        setExternalLink(result.link)
        setShowAddExternalEntity(false)
        setShowCompleteExternalModal(true)
        await openExternalAuthLink(result.link)
      }
    } catch {
      // ignore errors
    } finally {
      setConnectingInstitutionId(null)
    }
  }

  // Continue link for externally provided entities that require login
  const handleContinueExternalEntityLink = async (entity: any) => {
    if (!entity.external_entity_id) return
    setLinkingExternalEntityId(entity.id)
    try {
      const result: ExternalEntityConnectionResult =
        await connectExternalEntity({
          external_entity_id: entity.external_entity_id,
          completion_url: buildWebCompletionUrl(),
        })
      if (result.code === ExternalEntitySetupResponseCode.ALREADY_LINKED) {
        await fetchEntities()
      } else if (
        result.code === ExternalEntitySetupResponseCode.CONTINUE_WITH_LINK &&
        result.link &&
        result.id
      ) {
        setExternalEntityId(result.id)
        setExternalCompleteProvider(entity.provider ?? null)
        setExternalLink(result.link)
        setShowCompleteExternalModal(true)
        await openExternalAuthLink(result.link)
      }
    } catch {
      // ignore
    } finally {
      setLinkingExternalEntityId(null)
    }
  }

  const handleDisconnectExternalProvided = async (entity: any) => {
    if (!entity.external_entity_id) return
    try {
      await disconnectExternalEntity(entity.external_entity_id)
      await fetchEntities()
    } catch {
      // ignore
    }
  }

  const handleRelinkExternalProvided = async (entity: any) => {
    if (!entity.external_entity_id) return
    setLinkingExternalEntityId(entity.id)
    try {
      const result: ExternalEntityConnectionResult =
        await connectExternalEntity({
          external_entity_id: entity.external_entity_id,
          relink: true,
          completion_url: buildWebCompletionUrl(),
        })
      if (result.code === ExternalEntitySetupResponseCode.ALREADY_LINKED) {
        await fetchEntities()
      } else if (
        result.code === ExternalEntitySetupResponseCode.CONTINUE_WITH_LINK &&
        result.link &&
        result.id
      ) {
        setExternalEntityId(result.id)
        setExternalCompleteProvider(entity.provider ?? null)
        setExternalLink(result.link)
        setShowCompleteExternalModal(true)
        await openExternalAuthLink(result.link)
      }
    } catch {
      // ignore
    } finally {
      setLinkingExternalEntityId(null)
    }
  }

  const handleCompleteExternalConnection = async () => {
    if (!externalEntityId) return
    setCompletingConnection(true)
    try {
      await completeExternalEntityConnection(externalEntityId)
      await fetchEntities()
      setView("entities")
      setShowCompleteExternalModal(false)
    } catch {
      showToast(t.entities.externalLinkError, "error")
    } finally {
      setCompletingConnection(false)
    }
  }

  const handleExternalCompleteUrl = useCallback(
    async (url: string) => {
      if (!url.startsWith("finanze://external/complete")) return
      let code: string | null
      let state: string | null
      let error: string | null
      try {
        const urlObj = new URL(url)
        code = urlObj.searchParams.get("code")
        state = urlObj.searchParams.get("state")
        error = urlObj.searchParams.get("error")
      } catch {
        return
      }

      const entityId = state || externalEntityId
      if (error || !entityId) {
        await closeExternalAuthBrowser()
        setShowCompleteExternalModal(false)
        showToast(t.entities.externalLinkError, "error")
        return
      }

      await closeExternalAuthBrowser()
      setCompletingConnection(true)
      try {
        await completeExternalEntityConnection(entityId, code)
        await fetchEntities()
        setShowCompleteExternalModal(false)
        setView("entities")
        showToast(t.entities.externalLinkSuccess, "success")
      } catch {
        showToast(t.entities.externalLinkError, "error")
      } finally {
        setCompletingConnection(false)
      }
    },
    [externalEntityId, fetchEntities, setView, showToast, t],
  )

  // Listen for the external entity completion deep link (desktop)
  useEffect(() => {
    if (!window.ipcAPI?.onExternalCompleteUrl) return
    const unsubscribe = window.ipcAPI.onExternalCompleteUrl(async payload => {
      await handleExternalCompleteUrl(payload.url)
    })
    return () => unsubscribe?.()
  }, [handleExternalCompleteUrl])

  // Listen for the external entity completion deep link (mobile)
  useEffect(() => {
    if (!isNativeMobile()) return

    let cleanup: (() => void) | undefined
    let mounted = true

    import("@capacitor/app").then(({ App }) => {
      if (!mounted) return
      const listener = App.addListener("appUrlOpen", ({ url }) => {
        void handleExternalCompleteUrl(url)
      })
      cleanup = () => {
        listener.then(l => l.remove())
      }
    })

    return () => {
      mounted = false
      cleanup?.()
    }
  }, [handleExternalCompleteUrl])

  // Handle the external entity completion return (web/Docker). The provider
  // page redirects the browser back to this app with the code/state in the
  // query string; pick them up on mount and complete the connection.
  useEffect(() => {
    if (!isWeb()) return
    const params = new URLSearchParams(window.location.search)
    const code = params.get("code")
    const state = params.get("state")
    const error = params.get("error")
    if (!code && !state && !error) return

    const out = new URLSearchParams()
    if (code) out.set("code", code)
    if (state) out.set("state", state)
    if (error) out.set("error", error)
    void handleExternalCompleteUrl(
      `finanze://external/complete?${out.toString()}`,
    )

    window.history.replaceState(
      {},
      "",
      window.location.pathname + window.location.hash,
    )
  }, [handleExternalCompleteUrl])

  // Load candidate icons when list changes
  useEffect(() => {
    let cancelled = false
    const load = async () => {
      const entries: [string, string][] = []
      for (const c of externalCandidates) {
        if (!c.icon) continue
        try {
          const src = c.icon
            ? c.icon.startsWith("/")
              ? await getImageUrl(c.icon)
              : c.icon
            : ""
          if (!cancelled && src) entries.push([c.id, src])
        } catch {
          // ignore
        }
      }
      if (!cancelled && entries.length > 0) {
        setCandidateIcons(prev => ({ ...prev, ...Object.fromEntries(entries) }))
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [externalCandidates])

  const dismissCompleteModal = async () => {
    setShowCompleteExternalModal(false)
    try {
      await fetchEntities()
    } catch {
      /* ignore */
    }
    setView("entities")
  }

  return {
    // Providers
    enabledEntityProviders,
    hasProviderIntegration,
    hasAvailableEntityProvider,
    // Add external entity modal state
    showAddExternalEntity,
    selectedProvider,
    selectedCountry,
    candidatesLoading,
    candidatesError,
    externalCandidates,
    connectingInstitutionId,
    candidateIcons,
    institutionSearch,
    setInstitutionSearch,
    alreadyLinked,
    ebConfirmInstitutionId,
    setEbConfirmInstitutionId,
    // Complete modal state
    showCompleteExternalModal,
    externalLink,
    externalCompleteProvider,
    completingConnection,
    // Linking existing externally provided entity
    linkingExternalEntityId,
    // Handlers
    openAddExternalEntity,
    closeAddExternalEntity,
    handleSelectProvider,
    fetchCandidates,
    handleChangeCountry,
    handleConnectExternalEntity,
    handleContinueExternalEntityLink,
    handleDisconnectExternalProvided,
    handleRelinkExternalProvided,
    handleCompleteExternalConnection,
    dismissCompleteModal,
  }
}

export type ExternalEntityConnection = ReturnType<
  typeof useExternalEntityConnection
>

export function ExternalEntityConnectionModals({
  conn,
}: {
  conn: ExternalEntityConnection
}) {
  const { t } = useI18n()
  const {
    enabledEntityProviders,
    showAddExternalEntity,
    selectedProvider,
    selectedCountry,
    candidatesLoading,
    candidatesError,
    externalCandidates,
    connectingInstitutionId,
    candidateIcons,
    institutionSearch,
    setInstitutionSearch,
    alreadyLinked,
    ebConfirmInstitutionId,
    setEbConfirmInstitutionId,
    showCompleteExternalModal,
    externalLink,
    externalCompleteProvider,
    completingConnection,
    closeAddExternalEntity,
    handleSelectProvider,
    fetchCandidates,
    handleChangeCountry,
    handleConnectExternalEntity,
    handleCompleteExternalConnection,
    dismissCompleteModal,
  } = conn

  return (
    <>
      {/* Add External Entity Modal */}
      <AnimatePresence>
        {showAddExternalEntity && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[70] p-4"
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-white dark:bg-black rounded-lg shadow-2xl border border-gray-200 dark:border-gray-700 w-full max-w-4xl max-h-[85vh] flex flex-col"
            >
              <div className="flex flex-col h-full min-h-0">
                <div className="px-6 pt-6 pb-4 border-b border-gray-200 dark:border-gray-700">
                  <h3 className="text-lg font-semibold">
                    {t.entities.addExternalEntity}
                  </h3>
                </div>
                <div className="flex-1 overflow-y-auto p-6 space-y-8 min-h-0">
                  {enabledEntityProviders.length > 1 && (
                    <div>
                      <h4 className="text-sm font-medium mb-2">
                        {t.entities.selectProvider}
                      </h4>
                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                        {enabledEntityProviders.map(provider => (
                          <button
                            key={provider.id}
                            onClick={() => handleSelectProvider(provider.id)}
                            className={`border rounded-md py-3 px-3 text-sm font-medium transition-colors flex items-center justify-center gap-2 ${selectedProvider === provider.id ? "bg-gray-200 dark:bg-gray-800 border-gray-400 dark:border-gray-600" : "hover:bg-gray-100 dark:hover:bg-gray-900 border-gray-200 dark:border-gray-700"}`}
                          >
                            <AdaptiveLogo
                              src={`icons/external-integrations/${provider.id}.png`}
                              alt={provider.name}
                              className="w-6 h-6 rounded-md flex items-center justify-center overflow-hidden flex-shrink-0"
                              imgClassName="w-6 h-6 object-contain"
                              lightBgClassName="bg-white p-0.5"
                            />
                            <span className="truncate">{provider.name}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  {enabledEntityProviders.length === 1 && (
                    <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                      <AdaptiveLogo
                        src={`icons/external-integrations/${enabledEntityProviders[0].id}.png`}
                        alt={enabledEntityProviders[0].name}
                        className="w-5 h-5 rounded flex items-center justify-center overflow-hidden flex-shrink-0"
                        imgClassName="w-5 h-5 object-contain"
                        lightBgClassName="bg-white p-0.5"
                      />
                      <span className="truncate">
                        {t.entities.via.replace(
                          "{provider}",
                          enabledEntityProviders[0].name,
                        )}
                      </span>
                    </div>
                  )}
                  {selectedProvider && (
                    <div>
                      <h4 className="text-sm font-medium mb-2">
                        {t.entities.selectCountry}
                      </h4>
                      {selectedCountry ? (
                        <div className="flex items-center justify-between gap-2 border rounded-md px-3 py-2 border-gray-200 dark:border-gray-700">
                          <div className="flex items-center gap-2 min-w-0">
                            <span className="text-xl leading-none">
                              {getCountryFlag(selectedCountry)}
                            </span>
                            <span className="text-sm font-medium">
                              {selectedCountry}
                            </span>
                          </div>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={handleChangeCountry}
                          >
                            {t.entities.changeCountry}
                          </Button>
                        </div>
                      ) : (
                        <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 lg:grid-cols-10 gap-2">
                          {AVAILABLE_COUNTRIES.filter(
                            code => code !== "XX",
                          ).map(code => (
                            <button
                              key={code}
                              onClick={() => fetchCandidates(code)}
                              className="border rounded-md py-2 text-sm flex flex-col items-center justify-center gap-1 transition-colors hover:bg-gray-100 dark:hover:bg-gray-800 border-gray-200 dark:border-gray-700"
                            >
                              <span className="text-xl leading-none">
                                {getCountryFlag(code)}
                              </span>
                              <span className="text-[10px] font-medium">
                                {code}
                              </span>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                  {selectedProvider && selectedCountry && (
                    <div>
                      <h4 className="text-sm font-medium mb-2">
                        {t.entities.selectInstitution}
                      </h4>
                      {candidatesLoading && (
                        <div className="py-8 flex justify-center">
                          <LoadingSpinner size="lg" />
                        </div>
                      )}
                      {candidatesError && (
                        <div className="text-sm text-red-600 dark:text-red-400">
                          {candidatesError}
                        </div>
                      )}
                      {!candidatesLoading &&
                        !candidatesError &&
                        externalCandidates.length > 0 && (
                          <div className="relative mb-3">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
                            <Input
                              value={institutionSearch}
                              onChange={e =>
                                setInstitutionSearch(e.target.value)
                              }
                              placeholder={t.entities.searchInstitutions}
                              className="pl-9"
                            />
                          </div>
                        )}
                      {!candidatesLoading &&
                        !candidatesError &&
                        (() => {
                          const query = institutionSearch.trim().toLowerCase()
                          const filteredCandidates = query
                            ? externalCandidates.filter(
                                c =>
                                  c.name.toLowerCase().includes(query) ||
                                  (c.bic || "").toLowerCase().includes(query),
                              )
                            : externalCandidates
                          return (
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                              {filteredCandidates.length === 0 && (
                                <div className="text-sm text-gray-500 dark:text-gray-400 col-span-full">
                                  {t.entities.noInstitutionsFound}
                                </div>
                              )}
                              {filteredCandidates.map(c => {
                                const isConnecting =
                                  connectingInstitutionId === c.id
                                const iconSrc = candidateIcons[c.id]
                                return (
                                  <Card
                                    key={c.id}
                                    className={`p-4 cursor-pointer flex items-center gap-4 h-20 border border-gray-200 dark:border-gray-700 hover:border-primary/60 dark:hover:border-primary/60 transition-colors group`}
                                    onClick={() => {
                                      if (
                                        connectingInstitutionId &&
                                        connectingInstitutionId !== c.id
                                      )
                                        return
                                      if (
                                        selectedProvider ===
                                        ENABLE_BANKING_PROVIDER
                                      ) {
                                        setEbConfirmInstitutionId(c.id)
                                        return
                                      }
                                      handleConnectExternalEntity(c.id)
                                    }}
                                  >
                                    {isConnecting ? (
                                      <div className="w-full flex flex-col items-center justify-center gap-2">
                                        <LoadingSpinner size="sm" />
                                        <span className="text-xs text-gray-600 dark:text-gray-300">
                                          {t.entities.connecting}
                                        </span>
                                      </div>
                                    ) : (
                                      <>
                                        <div className="w-10 h-10 rounded-md flex items-center justify-center overflow-hidden flex-shrink-0">
                                          {iconSrc ? (
                                            <AdaptiveLogo
                                              src={iconSrc}
                                              alt={c.name}
                                              className="w-10 h-10 rounded-md flex items-center justify-center overflow-hidden"
                                              imgClassName="w-10 h-10 object-contain"
                                              lightBgClassName="bg-white p-0.5"
                                            />
                                          ) : (
                                            <Landmark className="h-5 w-5 text-gray-500" />
                                          )}
                                        </div>
                                        <div className="min-w-0 flex-1">
                                          <div className="font-medium truncate group-hover:text-primary">
                                            {c.name}
                                          </div>
                                          <div className="text-xs text-gray-500 dark:text-gray-400 mt-1 truncate">
                                            {c.bic}
                                          </div>
                                        </div>
                                      </>
                                    )}
                                  </Card>
                                )
                              })}
                            </div>
                          )
                        })()}
                      {alreadyLinked && (
                        <div className="mt-4 text-sm flex items-center gap-2 text-green-600 dark:text-green-400">
                          <Check className="h-4 w-4" />
                          {t.entities.alreadyLinked}
                        </div>
                      )}
                    </div>
                  )}
                </div>
                <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700 flex justify-end">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={closeAddExternalEntity}
                  >
                    {t.common.close}
                  </Button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <ConfirmationDialog
        isOpen={!!ebConfirmInstitutionId}
        title={t.entities.enableBankingPrelinkTitle}
        message={
          <span>
            {t.entities.enableBankingPrelinkMessageBefore}{" "}
            <a
              href="https://enablebanking.com/cp/applications"
              target="_blank"
              rel="noopener noreferrer"
              className="underline text-primary"
            >
              {t.entities.enableBankingPrelinkMessageLinkLabel}
            </a>
            {t.entities.enableBankingPrelinkMessageAfter}
          </span>
        }
        warning={<span>{t.entities.enableBankingPrelinkWarning}</span>}
        confirmText={t.common.confirm}
        cancelText={t.common.cancel}
        onConfirm={() => {
          const id = ebConfirmInstitutionId
          setEbConfirmInstitutionId(null)
          if (id) handleConnectExternalEntity(id)
        }}
        onCancel={() => setEbConfirmInstitutionId(null)}
      />

      {/* Complete External Entity Connection Modal */}
      <AnimatePresence>
        {showCompleteExternalModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[70] p-4"
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-white dark:bg-black rounded-lg shadow-2xl border border-gray-200 dark:border-gray-700 w-full max-w-md overflow-hidden"
            >
              <div className="p-6 space-y-4">
                <h3 className="text-lg font-semibold">
                  {t.entities.confirmConnection}
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  {t.entities.providerLinkInstructions}
                </p>
                <div className="flex flex-col gap-2">
                  {externalLink && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        try {
                          window.open(externalLink, "_blank")
                        } catch {
                          // ignore
                        }
                      }}
                    >
                      {t.entities.openLink}
                    </Button>
                  )}
                  {externalCompleteProvider !== ENABLE_BANKING_PROVIDER && (
                    <Button
                      size="sm"
                      onClick={handleCompleteExternalConnection}
                      disabled={completingConnection}
                    >
                      {completingConnection
                        ? t.common.loading
                        : t.entities.confirmConnection}
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={dismissCompleteModal}
                  >
                    {t.entities.dismiss}
                  </Button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
