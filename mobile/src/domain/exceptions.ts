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

export enum UnsupportedDatabaseDirection {
  OLD = "OLD",
  NEW = "NEW",
}

export class UnsupportedDatabaseVersion extends DomainError {
  public readonly direction: UnsupportedDatabaseDirection
  public readonly foundVersion: number | null
  public readonly supported: { min: number; max: number }

  constructor(params: {
    direction: UnsupportedDatabaseDirection
    foundVersion: number | null
    supported: { min: number; max: number }
    message?: string
  }) {
    const defaultMessage =
      params.direction === UnsupportedDatabaseDirection.OLD
        ? "Database version is too old"
        : "Database version is too new"

    super(params.message ?? defaultMessage)
    this.name = "UnsupportedDatabaseVersion"
    this.direction = params.direction
    this.foundVersion = params.foundVersion
    this.supported = params.supported
  }
}
