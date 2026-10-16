export enum AITask {
  LABELING = "LABELING",
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
