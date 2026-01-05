import { AuthPort } from "@/application/ports"
import { AuthProvider } from "./authProvider"
import { AuthStateChangeCallback, CloudSession } from "@/domain"

export class AuthPortAdapter implements AuthPort {
  constructor(private authProvider: AuthProvider) {}

  async initialize(): Promise<void> {
    await this.authProvider.initialize()
  }

  async getSession(): Promise<CloudSession | null> {
    return this.authProvider.getSession()
  }

  onAuthStateChange(callback: AuthStateChangeCallback): () => void {
    return this.authProvider.onAuthStateChange(callback)
  }

  async signInWithEmail(email: string, password: string): Promise<void> {
    await this.authProvider.signInWithEmail(email, password)
  }

  async signInWithGoogle(): Promise<void> {
    await this.authProvider.signInWithGoogle()
  }

  async signOut(): Promise<void> {
    await this.authProvider.signOut()
  }
}
