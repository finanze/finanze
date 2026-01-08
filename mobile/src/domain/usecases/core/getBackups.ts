import { BackupsInfoRequest, FullBackupsInfo } from "@/domain"

export interface GetBackups {
  execute(request: BackupsInfoRequest): Promise<FullBackupsInfo>
}
