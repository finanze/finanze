import { AuthStateChangeCallback } from "../cloudAuth"

export interface ObserveAuthState {
  execute(callback: AuthStateChangeCallback): () => void
}
