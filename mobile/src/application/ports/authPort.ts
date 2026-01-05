import { AuthStateChangeCallback, CloudSession } from "@/domain"

export interface AuthPort {
  initialize(): Promise<void>
  getSession(): Promise<CloudSession | null>
  onAuthStateChange(callback: AuthStateChangeCallback): () => void

  signInWithEmail(email: string, password: string): Promise<void>
  signInWithGoogle(): Promise<void>
  signOut(): Promise<void>
}
