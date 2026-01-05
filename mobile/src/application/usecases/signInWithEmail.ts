import { AuthPort } from "../ports"
import type { SignInWithEmail } from "@/domain/usecases"

export class SignInWithEmailImpl implements SignInWithEmail {
  constructor(private authPort: AuthPort) {}

  async execute(email: string, password: string): Promise<void> {
    await this.authPort.signInWithEmail(email, password)
  }
}
