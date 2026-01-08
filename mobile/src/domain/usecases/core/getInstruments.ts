import { InstrumentDataRequest, InstrumentOverview } from "@/domain"

export interface GetInstruments {
  execute(request: InstrumentDataRequest): Promise<InstrumentOverview[]>
}
