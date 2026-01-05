export class DomainError extends Error {
  constructor(message: string) {
    super(message)
    this.name = "DomainError"
  }
}

export class InvalidBackupCredentials extends DomainError {
  constructor(message: string = "Invalid backup credentials") {
    super(message)
    this.name = "InvalidBackupCredentials"
  }
}

export class TooManyRequests extends DomainError {
  constructor(message: string = "Too many requests") {
    super(message)
    this.name = "TooManyRequests"
  }
}

export class BackupConflict extends DomainError {
  constructor(message: string = "Backup conflict detected") {
    super(message)
    this.name = "BackupConflict"
  }
}

export class NotAuthenticated extends DomainError {
  constructor(message: string = "Not authenticated") {
    super(message)
    this.name = "NotAuthenticated"
  }
}

export class PermissionDenied extends DomainError {
  constructor(permission: string, message?: string) {
    super(message ?? `Permission denied: ${permission}`)
    this.name = "PermissionDenied"
  }
}
