import { AuthStateChangeCallback } from "@/domain"
import { AuthPort } from "../ports"
import type { ObserveAuthState } from "@/domain/usecases"

export class ObserveAuthStateImpl implements ObserveAuthState {
  constructor(private authPort: AuthPort) {}

  execute(callback: AuthStateChangeCallback): () => void {
    return this.authPort.onAuthStateChange(callback)
  }
}
