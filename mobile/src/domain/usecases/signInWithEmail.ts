export interface SignInWithEmail {
  execute(email: string, password: string): Promise<void>
}
