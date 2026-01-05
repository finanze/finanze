import { CloudAuthData } from "@/domain/core/cloudAuth"
import { AuthProvider } from "./authProvider"
import { CloudRegister } from "@/application/ports"

export class CloudRegisterAdapter implements CloudRegister {
  constructor(private authProvider: AuthProvider) {}

  async getAuth(): Promise<CloudAuthData | null> {
    try {
      const session = await this.authProvider.getSession()

      if (!session) {
        return null
      }

      return {
        token: { ...session },
        role: session.user.role,
        permissions: session.user.permissions,
        email: session.user.email,
      }
    } catch {
      return null
    }
  }
}
