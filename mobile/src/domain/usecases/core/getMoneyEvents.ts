import { MoneyEventQuery, MoneyEvents } from "@/domain"

export interface GetMoneyEvents {
  execute(query: MoneyEventQuery): Promise<MoneyEvents>
}
