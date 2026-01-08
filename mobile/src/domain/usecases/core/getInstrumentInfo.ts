import { InstrumentDataRequest, InstrumentInfo } from "@/domain"

export interface GetInstrumentInfo {
  execute(request: InstrumentDataRequest): Promise<InstrumentInfo | null>
}
