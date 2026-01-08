import { Settings } from "@/domain"

export interface UpdateSettings {
  execute(newConfig: Settings): Promise<void>
}
