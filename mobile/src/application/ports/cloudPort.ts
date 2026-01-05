import { CloudAuthData } from "@/domain"

export interface CloudRegister {
  getAuth(): Promise<CloudAuthData | null>
}
