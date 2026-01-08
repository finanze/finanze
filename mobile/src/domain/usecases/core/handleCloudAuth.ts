import { CloudAuthRequest, CloudAuthResponse } from "@/domain"

export interface HandleCloudAuth {
  execute(request: CloudAuthRequest): Promise<CloudAuthResponse>
}
