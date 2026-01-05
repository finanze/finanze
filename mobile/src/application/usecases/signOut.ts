import { AuthPort } from "../ports"
import type { SignOut } from "@/domain/usecases"

export class SignOutImpl implements SignOut {
  constructor(private authPort: AuthPort) {}

  async execute(): Promise<void> {
    await this.authPort.signOut()
  }
}
