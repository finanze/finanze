export type CacheEntry<V> = {
  value: V
  expiresAt: number
}

export class TtlCache<K, V> {
  private store = new Map<K, CacheEntry<V>>()

  constructor(
    private readonly maxSize: number,
    private readonly ttlMs: number,
  ) {}

  get(key: K): V | undefined {
    const entry = this.store.get(key)
    if (!entry) return undefined

    if (Date.now() >= entry.expiresAt) {
      this.store.delete(key)
      return undefined
    }

    return entry.value
  }

  has(key: K): boolean {
    return this.get(key) !== undefined
  }

  set(key: K, value: V): void {
    if (this.store.has(key)) {
      this.store.delete(key)
    }

    this.store.set(key, { value, expiresAt: Date.now() + this.ttlMs })

    while (this.store.size > this.maxSize) {
      const oldestKey = this.store.keys().next().value as K | undefined
      if (oldestKey === undefined) break
      this.store.delete(oldestKey)
    }
  }

  delete(key: K): void {
    this.store.delete(key)
  }

  clear(): void {
    this.store.clear()
  }
}
