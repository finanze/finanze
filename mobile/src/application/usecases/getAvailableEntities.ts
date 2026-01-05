import {
  AvailableSource,
  AvailableSources,
  EntityOrigin,
  EntityType,
  ExternalEntityStatus,
  Feature,
  FinancialEntityStatus,
  ProductType,
  VirtualDataImport,
} from "@/domain"
import { NATIVE_ENTITIES } from "@/domain/nativeEntities"
import {
  CredentialsPort,
  CryptoWalletConnectionPort,
  EntityPort,
  ExternalEntityPort,
  LastFetchesPort,
  VirtualImportRegistry,
} from "../ports"
import { GetAvailableEntities } from "@/domain/usecases"

function getLastFetchesForVirtual(
  virtualImports: VirtualDataImport[],
): Partial<Record<Feature, string>> {
  const lastFetch: Partial<Record<Feature, string>> = {}
  for (const virtualImport of virtualImports) {
    if (!virtualImport.feature) continue
    lastFetch[virtualImport.feature] = virtualImport.date
  }
  return lastFetch
}

const EXTERNAL_ENTITY_FEATURES: Feature[] = [Feature.POSITION]

export class GetAvailableEntitiesImpl implements GetAvailableEntities {
  private static readonly LISTED_ENTITY_TYPES: EntityType[] = [
    EntityType.FINANCIAL_INSTITUTION,
    EntityType.CRYPTO_EXCHANGE,
    EntityType.CRYPTO_WALLET,
  ]

  private static readonly EXTERNAL_ENTITY_PRODUCTS: ProductType[] = [
    ProductType.ACCOUNT,
  ]
  private static readonly CRYPTO_WALLET_PRODUCTS: ProductType[] = [
    ProductType.CRYPTO,
  ]

  constructor(
    private entityPort: EntityPort,
    private externalEntityPort: ExternalEntityPort,
    private credentialsPort: CredentialsPort,
    private cryptoWalletConnectionsPort: CryptoWalletConnectionPort,
    private lastFetchesPort: LastFetchesPort,
    private virtualImportRegistry: VirtualImportRegistry,
  ) {}

  async execute(): Promise<AvailableSources> {
    const loggedEntities = await this.credentialsPort.getAvailableEntities()
    const loggedEntityIds = new Map<string, string | null>()
    for (const e of loggedEntities) {
      loggedEntityIds.set(e.entityId, e.expiration ?? null)
    }

    const allEntities = await this.entityPort.getAll()

    const nativeEntitiesById = new Map(
      NATIVE_ENTITIES.filter(e => !!e.id).map(e => [e.id as string, e]),
    )

    const lastVirtualImportedEntities =
      await this.getLastVirtualImportsByEntity()

    const entities: AvailableSource[] = []
    for (const entity of allEntities) {
      if (!entity.id) {
        continue
      }

      if (
        !entity.type ||
        !GetAvailableEntitiesImpl.LISTED_ENTITY_TYPES.includes(entity.type)
      ) {
        continue
      }

      const nativeEntity = nativeEntitiesById.get(entity.id)

      let status: FinancialEntityStatus | null = null
      let wallets: any = null
      let externalEntityId: string | null = null
      let products: ProductType[] | null | undefined = null

      const lastVirtualImportedData = lastVirtualImportedEntities.get(entity.id)
      let virtualFeatures: Partial<Record<Feature, string>> = {}
      if (lastVirtualImportedData && lastVirtualImportedData.length > 0) {
        virtualFeatures = getLastFetchesForVirtual(lastVirtualImportedData)
      }

      const dictEntity: any = { ...(nativeEntity ?? entity) }

      if (entity.origin === EntityOrigin.EXTERNALLY_PROVIDED) {
        products = GetAvailableEntitiesImpl.EXTERNAL_ENTITY_PRODUCTS
        const externalEntity = await this.externalEntityPort.getByEntityId(
          entity.id,
        )
        if (!externalEntity) {
          status = FinancialEntityStatus.DISCONNECTED
          dictEntity.features = []
        } else {
          status =
            externalEntity.status === ExternalEntityStatus.LINKED
              ? FinancialEntityStatus.CONNECTED
              : FinancialEntityStatus.REQUIRES_LOGIN
          externalEntityId = externalEntity.id
          dictEntity.features = EXTERNAL_ENTITY_FEATURES
        }
      } else if (
        entity.type === EntityType.FINANCIAL_INSTITUTION ||
        entity.type === EntityType.CRYPTO_EXCHANGE
      ) {
        status = FinancialEntityStatus.DISCONNECTED
        products = dictEntity.products

        if (entity.origin !== EntityOrigin.MANUAL) {
          if (loggedEntityIds.has(entity.id)) {
            status = FinancialEntityStatus.CONNECTED

            const expiration = loggedEntityIds.get(entity.id)
            if (expiration) {
              const expirationDate = new Date(expiration)
              if (expirationDate < new Date()) {
                status = FinancialEntityStatus.REQUIRES_LOGIN
              }
            }
          }
        } else {
          if (Object.keys(virtualFeatures).length > 0) {
            status = FinancialEntityStatus.CONNECTED
          }
        }
      } else {
        wallets = await this.cryptoWalletConnectionsPort.getByEntityId(
          entity.id,
        )
        products = GetAvailableEntitiesImpl.CRYPTO_WALLET_PRODUCTS
      }

      let lastFetch: Partial<Record<Feature, string>> = {}
      if (entity.origin !== EntityOrigin.MANUAL) {
        if (status !== FinancialEntityStatus.DISCONNECTED) {
          const lastFetchRecords = await this.lastFetchesPort.getByEntityId(
            entity.id,
          )
          lastFetch = Object.fromEntries(
            lastFetchRecords
              .filter(r => !!r.feature)
              .map(r => [r.feature as Feature, r.date]),
          )
        }
      } else {
        dictEntity.features = []
      }

      const entityVirtualImports = lastVirtualImportedEntities.get(entity.id)
      if (entityVirtualImports && entityVirtualImports.length > 0) {
        const virtualLastFetch = getLastFetchesForVirtual(entityVirtualImports)
        if (entity.origin === EntityOrigin.MANUAL) {
          lastFetch = virtualLastFetch
          dictEntity.features = Object.keys(virtualLastFetch) as Feature[]
        }
      }

      entities.push({
        ...dictEntity,
        status,
        connected: wallets,
        lastFetch,
        requiredExternalIntegrations:
          dictEntity.requiredExternalIntegrations ?? [],
        externalEntityId,
        virtualFeatures,
        nativelySupportedProducts: products ?? null,
      })
    }

    return { entities }
  }

  private async getLastVirtualImportsByEntity(): Promise<
    Map<string, VirtualDataImport[]>
  > {
    const lastVirtualImports =
      await this.virtualImportRegistry.getLastImportRecords()
    const lastVirtualImportedEntities = new Map<string, VirtualDataImport[]>()
    for (const virtualImport of lastVirtualImports) {
      if (!virtualImport.entityId) continue
      const list = lastVirtualImportedEntities.get(virtualImport.entityId) ?? []
      list.push(virtualImport)
      lastVirtualImportedEntities.set(virtualImport.entityId, list)
    }
    return lastVirtualImportedEntities
  }
}
