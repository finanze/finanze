import { CloudSession } from "@/domain"
import { AuthPort } from "../ports"
import type { GetAuthSession } from "@/domain/usecases"

export class GetAuthSessionImpl implements GetAuthSession {
  constructor(private authPort: AuthPort) {}

  async execute(): Promise<CloudSession | null> {
    return this.authPort.getSession()
  }
}
