import { CloudAuthData } from "@/domain"

export interface GetCloudAuth {
  execute(): Promise<CloudAuthData | null>
}
