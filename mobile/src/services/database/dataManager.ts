import * as SQLite from "expo-sqlite"

import * as FileSystem from "expo-file-system/legacy"
import { Buffer } from "buffer"
import { sha3_256 } from "@noble/hashes/sha3.js"
import { bytesToHex } from "@noble/hashes/utils.js"

import { DatabaseClient, DatabaseConfig, QueryResult } from "./types"
import {
  Backupable,
  DatasourceAdminPort,
  DatasourceInitiator,
} from "@/application/ports"
import {
  UnsupportedDatabaseVersion,
  UnsupportedDatabaseDirection,
} from "@/domain/exceptions"

const DB_NAME = "finanze.db"

const SUPPORTED_DB_VERSION = { min: 45, max: 45 }

/**
 * Hash password with SHA3-256 (matches Python's hashlib.sha3_256().hexdigest())
 */
function hashPassword(password: string): string {
  const passwordBuffer = Buffer.from(password, "utf-8")
  return bytesToHex(sha3_256(passwordBuffer))
}

export class DataManager
  implements
    DatabaseClient,
    DatasourceAdminPort,
    DatasourceInitiator,
    Backupable
{
  private db: SQLite.SQLiteDatabase | null = null
  private config: DatabaseConfig
  private encryptionKey: string | null = null
  private hashedPassword: string | null = null

  constructor(config: Partial<DatabaseConfig> = {}) {
    this.config = {
      name: DB_NAME,
      encrypted: true,
      location: config.location,
    }
  }

  async initialize(password: string): Promise<void> {
    if (this.db) {
      return
    }

    this.hashedPassword = hashPassword(password)
    this.encryptionKey = password

    const hasExistingDatabase = await this.exists()
    if (!hasExistingDatabase) {
      return
    }

    if (this.config.encrypted && !this.encryptionKey) {
      throw new Error("Missing encryption key")
    }

    this.db = await SQLite.openDatabaseAsync(
      this.config.name,
      { useNewConnection: true },
      this.config.location,
    )

    try {
      await this.configureOpenDatabase(this.db!)
      await this.db!.getFirstAsync("SELECT 1")
    } catch (error) {
      await this.close()
      throw new Error(`Failed to initialize database: ${error}`)
    }
  }

  async close(): Promise<void> {
    if (!this.db) {
      return
    }

    try {
      await this.db.closeAsync()
    } finally {
      this.db = null
    }
  }

  isOpen(): boolean {
    return this.db !== null
  }

  async query<T = any>(sql: string, params?: any[]): Promise<QueryResult<T>> {
    const db = this.getOpenDb()
    const rows = params
      ? await db.getAllAsync<T>(sql, params)
      : await db.getAllAsync<T>(sql)
    return { rows, rowCount: rows.length }
  }

  async execute(sql: string, params?: any[]): Promise<void> {
    const db = this.getOpenDb()
    if (params) {
      await db.runAsync(sql, params)
      return
    }
    await db.runAsync(sql)
  }

  async transaction<T>(callback: () => Promise<T>): Promise<T> {
    const db = this.getOpenDb()
    await db.execAsync("BEGIN")
    try {
      const result = await callback()
      await db.execAsync("COMMIT")
      return result
    } catch (error) {
      await db.execAsync("ROLLBACK")
      throw error
    }
  }

  async importData(data: Uint8Array): Promise<void> {
    if (this.config.encrypted && !this.encryptionKey) {
      throw new Error("Missing encryption key")
    }

    const sourceDb = await SQLite.deserializeDatabaseAsync(data)
    const destDatabasePath = this.getDatabasePath()

    const sourceVersion = await this.getDatabaseVersion(sourceDb)
    if (sourceVersion === null || sourceVersion < SUPPORTED_DB_VERSION.min) {
      await sourceDb.closeAsync()
      throw new UnsupportedDatabaseVersion({
        direction: UnsupportedDatabaseDirection.OLD,
        foundVersion: sourceVersion,
        supported: SUPPORTED_DB_VERSION,
      })
    }

    if (sourceVersion > SUPPORTED_DB_VERSION.max) {
      await sourceDb.closeAsync()
      throw new UnsupportedDatabaseVersion({
        direction: UnsupportedDatabaseDirection.NEW,
        foundVersion: sourceVersion,
        supported: SUPPORTED_DB_VERSION,
      })
    }

    try {
      await this.close()
      try {
        await SQLite.deleteDatabaseAsync(this.config.name, this.config.location)
      } catch {
        // Best-effort cleanup.
      }

      if (this.config.encrypted) {
        if (!this.encryptionKey) {
          throw new Error("Missing encryption key")
        }

        const escapedDestPath = destDatabasePath.replace(/'/g, "''")
        const escapedKey = this.sanitizePassword(this.encryptionKey)

        // Create an encrypted database file by exporting from the plaintext in-memory db.
        await sourceDb.execAsync(
          `ATTACH DATABASE '${escapedDestPath}' AS encrypted KEY '${escapedKey}'`,
        )
        await sourceDb.execAsync("SELECT sqlcipher_export('encrypted')")
        await sourceDb.execAsync("DETACH DATABASE encrypted")
      } else {
        const destDb = await SQLite.openDatabaseAsync(
          this.config.name,
          { useNewConnection: true },
          this.config.location,
        )

        try {
          await SQLite.backupDatabaseAsync({
            sourceDatabase: sourceDb,
            sourceDatabaseName: "main",
            destDatabase: destDb,
            destDatabaseName: "main",
          })
        } finally {
          await destDb.closeAsync()
        }
      }

      const reopenedDb = await SQLite.openDatabaseAsync(
        this.config.name,
        { useNewConnection: true },
        this.config.location,
      )

      await this.configureOpenDatabase(reopenedDb)
      this.db = reopenedDb
    } catch (error) {
      throw new Error(`Failed to import data: ${error}`)
    } finally {
      await sourceDb.closeAsync()

      if (this.encryptionKey) {
        await this.initialize(this.encryptionKey!)
      }
    }
  }

  async deleteDatabase(): Promise<void> {
    await this.close()
    try {
      await SQLite.deleteDatabaseAsync(this.config.name, this.config.location)
    } catch {
      // Best-effort delete.
    }

    this.encryptionKey = null
    this.hashedPassword = null
  }

  private getOpenDb(): SQLite.SQLiteDatabase {
    if (!this.db) {
      throw new Error("Database not initialized")
    }
    return this.db
  }

  private async configureOpenDatabase(
    db: SQLite.SQLiteDatabase,
  ): Promise<void> {
    if (this.config.encrypted) {
      if (!this.encryptionKey) {
        throw new Error("Missing encryption key")
      }
      await db.execAsync(
        `PRAGMA key = '${this.sanitizePassword(this.encryptionKey)}'`,
      )
    }

    await db.execAsync("PRAGMA journal_mode = WAL")
    await db.execAsync("PRAGMA foreign_keys = ON")
  }

  private sanitizePassword(password: string): string {
    return password.replace(/'/g, "''")
  }

  async getLastUpdated(): Promise<Date | null> {
    try {
      if (!this.exists()) {
        return null
      }

      const row = await this.getOpenDb().getFirstAsync<{ value: string }>(
        "SELECT value FROM sys_config WHERE \"key\" = 'last_update'",
      )
      if (!row?.value) {
        return null
      }
      const parsed = new Date(row.value)
      return Number.isFinite(parsed.getTime()) ? parsed : new Date(0)
    } catch (error) {
      console.warn("Local last update: error", error)
      return null
    }
  }

  async getHashedPassword(): Promise<string | null> {
    return this.hashedPassword
  }

  private getDatabasePath(): string {
    const directory =
      this.config.location ??
      (SQLite as unknown as { defaultDatabaseDirectory?: string })
        .defaultDatabaseDirectory

    if (!directory) {
      return this.config.name
    }

    const normalizedDirectory = directory.endsWith("/")
      ? directory.slice(0, -1)
      : directory
    const normalizedName = this.config.name.startsWith("/")
      ? this.config.name.slice(1)
      : this.config.name

    return `${normalizedDirectory}/${normalizedName}`
  }

  async exists(): Promise<boolean> {
    try {
      const path = this.getDatabasePath()
      const info = await FileSystem.getInfoAsync(path)
      return Boolean(info.exists)
    } catch {
      return false
    }
  }

  private async getDatabaseVersion(
    database: SQLite.SQLiteDatabase,
  ): Promise<number | null> {
    try {
      const row = await database.getFirstAsync<{ version: number }>(
        "SELECT MAX(version) AS version FROM migrations",
      )
      return row?.version ?? null
    } catch {
      return null
    }
  }
}
