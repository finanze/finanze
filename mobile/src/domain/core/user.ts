export interface User {
  id: string
  username: string
  path: string
  lastLogin: string | null
}

export interface UserRegistration {
  id: string
  username: string
}
