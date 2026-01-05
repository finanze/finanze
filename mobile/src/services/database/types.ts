/**
 * Database Client Interface
 *
 * This interface defines the contract for database operations.
 * Implementations can use SQLCipher, AsyncStorage, or any other storage mechanism.
 */

export interface QueryResult<T> {
  rows: T[]
  rowCount: number
}

export interface DatabaseClient {
  /**
   * Execute a read-only query
   */
  query<T = any>(sql: string, params?: any[]): Promise<QueryResult<T>>

  /**
   * Execute a write query (INSERT, UPDATE, DELETE)
   */
  execute(sql: string, params?: any[]): Promise<void>

  /**
   * Execute multiple statements in a transaction
   */
  transaction<T>(callback: () => Promise<T>): Promise<T>
}

/**
 * Database configuration options
 */
export interface DatabaseConfig {
  /** Database file name */
  name: string
  /** Enable encryption (SQLCipher) */
  encrypted: boolean
  /** Database location */
  location?: string
}
