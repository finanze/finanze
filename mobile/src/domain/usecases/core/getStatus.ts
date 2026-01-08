import { GlobalStatus } from "@/domain"

export interface GetStatus {
  execute(): Promise<GlobalStatus>
}
