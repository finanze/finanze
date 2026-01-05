import { AuthPort } from "../ports"
import type { InitializeAuth } from "@/domain/usecases"

export class InitializeAuthImpl implements InitializeAuth {
  constructor(private authPort: AuthPort) {}

  async execute(): Promise<void> {
    await this.authPort.initialize()
  }
}
