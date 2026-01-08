import {
  ConnectExternalEntityRequest,
  ExternalEntityConnectionResult,
} from "@/domain"

export interface ConnectExternalEntity {
  execute(
    request: ConnectExternalEntityRequest,
  ): Promise<ExternalEntityConnectionResult>
}
