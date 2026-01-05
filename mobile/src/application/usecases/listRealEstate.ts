import { RealEstate } from "@/domain"
import { RealEstatePort } from "../ports"
import { getNextDate } from "./getPeriodicFlows"
import { ListRealEstate } from "@/domain/usecases"

export class ListRealEstateImpl implements ListRealEstate {
  constructor(private realEstatePort: RealEstatePort) {}

  async execute(): Promise<RealEstate[]> {
    const entries = await this.realEstatePort.getAll()

    for (const entry of entries) {
      for (const flow of entry.flows) {
        if (flow.periodicFlow) {
          flow.periodicFlow.nextDate = getNextDate(flow.periodicFlow)
        }
      }
    }

    return entries
  }
}
