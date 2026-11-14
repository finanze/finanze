export enum AITask {
  LABELING = "LABELING",
  IMPORTING = "IMPORTING",
}

export enum AIInputModality {
  TEXT = "TEXT",
  IMAGE = "IMAGE",
  DOCUMENT = "DOCUMENT",
}

export const MAX_AI_PROVIDERS = 5

export interface AIProviderEntry {
  provider: string
  model: string
  upstreamProvider?: string | null
}

export interface AISettings {
  providers: AIProviderEntry[]
}

export interface AIImportSettings {
  providers: AIProviderEntry[]
  instructions?: string | null
}

export interface AICatalogModel {
  id: string
  name: string
  description?: string | null
  probabilistic: boolean
  size?: number | null
  loaded?: boolean
  load_failed?: boolean
  pricing?: AIModelPricing | null
  input_modalities?: AIInputModality[] | null
  eligible?: boolean | null
}

export interface AIProviderDetails {
  id: string
  connected: boolean
  recommended_models: AICatalogModel[]
  custom_models: boolean
  upstream_providers: boolean
  dynamic_models?: boolean
  attachments?: boolean
}

export interface AIProviders {
  providers: AIProviderDetails[]
}

export interface AIModels {
  models: AICatalogModel[]
}

export enum AIModelCapability {
  STRUCTURED_OUTPUT = "STRUCTURED_OUTPUT",
  TEMPERATURE = "TEMPERATURE",
  REASONING = "REASONING",
  DECISIONS = "DECISIONS",
}

export interface AIModelValidation {
  valid: boolean
  name?: string | null
  capabilities: AIModelCapability[]
  upstream_provider?: string | null
}

export interface AIModelPricing {
  input_per_million: number
  output_per_million: number
  currency: string
}

export enum AIServerKind {
  OLLAMA = "OLLAMA",
  LM_STUDIO = "LM_STUDIO",
  LLAMA_CPP = "LLAMA_CPP",
  VLLM = "VLLM",
}

export enum AIServerError {
  UNREACHABLE = "UNREACHABLE",
  UNAUTHORIZED = "UNAUTHORIZED",
  NOT_FOUND = "NOT_FOUND",
  SERVER_ERROR = "SERVER_ERROR",
  INVALID_RESPONSE = "INVALID_RESPONSE",
}

export interface AIServerModel {
  id: string
  decisions: boolean
  loaded?: boolean | null
  size?: number | null
  context_length?: number | null
}

export interface AIServerInfo {
  url: string
  api_key_set: boolean
  reachable: boolean
  error?: AIServerError | null
  latency_ms?: number | null
  kind?: AIServerKind | null
  version?: string | null
  models: AIServerModel[]
}

export enum LocalModelSource {
  CATALOG = "CATALOG",
  HUGGING_FACE = "HUGGING_FACE",
  IMPORTED = "IMPORTED",
  SERVER = "SERVER",
}

export enum LocalModelState {
  UNLOADED = "UNLOADED",
  LOADING = "LOADING",
  LOADED = "LOADED",
  SLEEPING = "SLEEPING",
  DOWNLOADING = "DOWNLOADING",
  FAILED = "FAILED",
  MISSING = "MISSING",
}

export enum LocalRuntimeMode {
  BUILT_IN = "BUILT_IN",
  EXTERNAL = "EXTERNAL",
}

export enum LocalRuntimeSource {
  PAYLOAD = "PAYLOAD",
  ENVIRONMENT = "ENVIRONMENT",
  BUILT_IN = "BUILT_IN",
}

export interface LocalModel {
  id: string
  name: string
  source: LocalModelSource
  state: LocalModelState
  size?: number | null
  downloaded?: number | null
  decisions: boolean
  deletable: boolean
  path?: string | null
}

export interface LocalModelCatalogEntry {
  id: string
  name: string
  repo: string
  quant: string
  size: number
  ram: number
  params: string
  license: string
  decisions: boolean
  languages?: string[] | null
}

export interface LocalModelsCapabilities {
  built_in_available: boolean
  can_import_files: boolean
  env_server_url?: string | null
  env_api_key_set: boolean
  system_memory?: number | null
}

export interface LocalModelsOverview {
  connected: boolean
  capabilities: LocalModelsCapabilities
  catalog: LocalModelCatalogEntry[]
  mode?: LocalRuntimeMode | null
  source?: LocalRuntimeSource | null
  server_url?: string | null
  reachable: boolean
  error?: string | null
  models: LocalModel[]
  models_folder?: string | null
}

export interface DownloadLocalModelRequest {
  catalog_id?: string
  repo?: string
  quant?: string
}

export interface HuggingFaceQuantOption {
  quant: string
  file: string
  size?: number | null
}

export enum HuggingFaceModelKind {
  DECISIONS = "DECISIONS",
  CHAT = "CHAT",
  ENCODER = "ENCODER",
  UNKNOWN = "UNKNOWN",
}

export interface HuggingFaceQuants {
  repo: string
  quants: HuggingFaceQuantOption[]
  kind: HuggingFaceModelKind
}

export interface ImportedLocalModel {
  id: string
  path: string
  exists: boolean
  size?: number | null
}
