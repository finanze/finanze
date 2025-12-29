import type { ReactNode } from "react"
import type { Entity, DataSource, ExchangeRates } from "@/types"
import type { EntitiesPosition, ProductType } from "@/types/position"

export type ManualPositionAsset =
  | "bankAccounts"
  | "bankCards"
  | "bankLoans"
  | "fundPortfolios"
  | "funds"
  | "stocks"
  | "deposits"
  | "factoring"
  | "realEstateCf"
  | "crypto"

export type ManualPositionDraft<Entry extends Record<string, any>> = Entry & {
  localId: string
  originalId?: string
  entityId: string
  entityName: string
  isNewEntity?: boolean
  newEntityName?: string | null
}

export interface ManualPositionFormBase {
  entity_id: string
  entity_mode: "select" | "new"
  new_entity_name: string
}

export type ManualFormErrors<FormState extends ManualPositionFormBase> =
  Partial<Record<keyof FormState, string>>

export interface ManualFormFieldRenderProps<
  FormState extends ManualPositionFormBase,
> {
  form: FormState
  updateField: (field: keyof FormState, value: string) => void
  errors: ManualFormErrors<FormState>
  clearError: (field: keyof FormState) => void
  t: (path: string, params?: Record<string, any>) => string
  entityOptions: Entity[]
  currencyOptions: string[]
  defaultCurrency: string
  locale: string
  mode: "create" | "edit"
  canEditEntity: boolean
  exchangeRates: ExchangeRates | null
  accountOptions?: (
    entityId?: string | null,
  ) => { value: string; label: string }[]
  portfolioOptions?: (entityId?: string | null) => {
    value: string
    label: string
    source: DataSource
    name?: string | null
    currency?: string | null
    isDraft?: boolean
    draftLocalId?: string
  }[]
}

export interface RenderSummaryHelpers {
  formatCurrency: (
    value: number | null | undefined,
    currency?: string,
    fallbackCurrency?: string,
  ) => string
  locale: string
  defaultCurrency: string
  t: (path: string, params?: Record<string, any>) => string
}

export interface ManualPositionConfig<
  Entry extends Record<string, any>,
  FormState extends ManualPositionFormBase,
> {
  assetKey: ManualPositionAsset
  productType: ProductType
  buildDraftsFromPositions: (params: {
    positionsData: EntitiesPosition | null
    manualEntities: Entity[]
  }) => ManualPositionDraft<Entry>[]
  createEmptyForm: (params: {
    defaultCurrency: string
    entityId?: string
  }) => FormState
  draftToForm: (draft: ManualPositionDraft<Entry>) => FormState
  buildEntryFromForm: (
    form: FormState,
    params: {
      previous?: ManualPositionDraft<Entry>
      defaultCurrency?: string
    },
  ) => Entry | null
  validateForm: (
    form: FormState,
    params: {
      t: (path: string, params?: Record<string, any>) => string
      currencyOptions: string[]
    },
  ) => ManualFormErrors<FormState>
  renderFormFields: (props: ManualFormFieldRenderProps<FormState>) => ReactNode
  getDisplayName: (draft: ManualPositionDraft<Entry>) => string
  renderDraftSummary: (
    draft: ManualPositionDraft<Entry>,
    helpers: RenderSummaryHelpers,
  ) => ReactNode
  normalizeDraftForCompare: (draft: ManualPositionDraft<Entry>) => unknown
  toPayloadEntry: (draft: ManualPositionDraft<Entry>) => Entry
}

export type ManualPositionConfigMap = Record<
  ManualPositionAsset,
  ManualPositionConfig<any, any>
>

export interface ManualSaveEntryPayload<Entry extends Record<string, any>> {
  payload: Entry
  draft: ManualPositionDraft<Entry>
}

export type ManualSavePayloadByEntity = Map<
  string,
  {
    productType: ProductType
    entries: ManualSaveEntryPayload<Record<string, any>>[]
    isNewEntity: boolean
    newEntityName?: string | null
    newEntityIconUrl?: string | null
    netCryptoEntityDetails?: {
      provider_asset_id: string
      provider: string
    } | null
  }
>
