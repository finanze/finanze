import { Settings } from "@/domain"

export interface GetSettings {
  execute(): Promise<Settings>
}
