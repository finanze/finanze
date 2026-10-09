import type { AccountTx, LabelOrigin, TxType } from "./transactions"

export enum LabelCategory {
  EXPENSE = "EXPENSE",
  INCOME = "INCOME",
  EXCLUDED = "EXCLUDED",
}

export interface Label {
  id: string
  key?: string | null
  name?: string | null
  description?: string | null
  color?: string | null
  icon?: string | null
  category: LabelCategory
  usage?: number | null
}

export interface LabelsResponse {
  labels: Label[]
}

export interface SaveLabelRequest {
  name?: string | null
  description?: string | null
  color?: string | null
  icon?: string | null
  category: LabelCategory
}

export enum TextMatchOperator {
  CONTAINS = "CONTAINS",
  STARTS_WITH = "STARTS_WITH",
  EQUALS = "EQUALS",
  REGEX = "REGEX",
}

export enum TextMatchField {
  ANY = "ANY",
  NAME = "NAME",
  COUNTERPARTY = "COUNTERPARTY",
}

export interface TextCondition {
  value: string
  operator: TextMatchOperator
  field: TextMatchField
}

export interface LabelingRuleConditions {
  types?: TxType[] | null
  min_amount?: number | null
  max_amount?: number | null
  currency?: string | null
  from_date?: string | null
  to_date?: string | null
  day_from?: number | null
  day_to?: number | null
  entities?: string[] | null
  text?: TextCondition | null
  max_days?: number | null
  ibans?: string[] | null
}

export enum LabelingRuleKind {
  MATCH = "MATCH",
  TRANSFER = "TRANSFER",
}

export interface LabelingRule {
  id: string
  name?: string | null
  enabled: boolean
  kind: LabelingRuleKind
  conditions: LabelingRuleConditions
  label_ids: string[]
}

export interface LabelingRulesResponse {
  rules: LabelingRule[]
}

export interface SaveLabelingRuleRequest {
  name?: string | null
  enabled: boolean
  kind?: LabelingRuleKind
  conditions: LabelingRuleConditions
  labels: string[]
  apply_to_existing: boolean
}

export interface SavedLabelingRule {
  rule: LabelingRule
  applied: number
}

export interface LabelingRulePreview {
  count: number
  samples: AccountTx[]
}

export interface UpdateTransactionLabelsRequest {
  labels: string[]
  locked: boolean
  unlink?: boolean
  unpair?: boolean
}

export interface RelabelRequest {
  from_date?: string
  to_date?: string
  entities?: string[]
  with_labels?: string[]
  without_labels?: string[]
  unlabeled_only?: boolean
  origins?: LabelOrigin[]
  include_external?: boolean
  retry_external_unmatched?: boolean
  dry_run?: boolean
}

export interface LabelingResult {
  processed: number
  linked: number
  paired: number
  rule_labeled: number
  external_labeled: number
  skipped_locked: number
  skipped_linked: number
  external_error?: string | null
  external_error_details?: string | null
}

export interface RelabelResult {
  matched: number
  result?: LabelingResult | null
  external?: LabelingResult | null
}

export interface ExternalLabelingModel {
  id: string
  name: string
  description?: string | null
  probabilistic: boolean
}

export interface ExternalLabelingProviderDetails {
  id: string
  connected: boolean
  recommended_models: ExternalLabelingModel[]
  custom_models: boolean
  upstream_providers: boolean
}

export interface ExternalLabelingProviders {
  providers: ExternalLabelingProviderDetails[]
}

export interface ExternalLabelingSettings {
  enabled: boolean
  provider?: string | null
  model?: string | null
  upstreamProvider?: string | null
  autoRun: boolean
  minConfidence: number
  maxPerRun: number
  examples: {
    enabled: boolean
    count: number
    origins: LabelOrigin[]
  }
  instructions?: string | null
}

export interface LabelingSettings {
  external: ExternalLabelingSettings
}
