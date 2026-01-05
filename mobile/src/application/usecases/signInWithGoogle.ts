import { AuthPort } from "../ports"
import type { SignInWithGoogle } from "@/domain/usecases"

export class SignInWithGoogleImpl implements SignInWithGoogle {
  constructor(private authPort: AuthPort) {}

  async execute(): Promise<void> {
    await this.authPort.signInWithGoogle()
  }
}
