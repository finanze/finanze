import { ForecastRequest, ForecastResult } from "@/domain"

export interface Forecast {
  execute(request: ForecastRequest): Promise<ForecastResult>
}
