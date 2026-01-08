import { BackupFileType } from "@/domain"

import type { Backupable } from "@/application/ports"
import type {
  CheckDatasourceExists,
  ClearLocalData,
  GetAuthSession,
  GetAvailableEntities,
  GetBackups,
  GetDefaultCurrency,
  GetLocalLastUpdate,
  GetPendingFlows,
  GetPosition,
  GetTransactions,
  ImportBackup,
  InitializeAuth,
  InitializeDatasource,
  ListRealEstate,
  ObserveAuthState,
  SignInWithEmail,
  SignInWithGoogle,
  SignOut,
  GetExchangeRates,
} from "@/domain/usecases"

import type { ApplicationContainer } from "@/domain/applicationContainer"

import {
  CheckDatasourceExistsImpl,
  ClearLocalDataImpl,
  GetAuthSessionImpl,
  GetAvailableEntitiesImpl,
  GetBackupsImpl,
  GetDefaultCurrencyImpl,
  GetExchangeRatesImpl,
  GetLocalLastUpdateImpl,
  GetPendingFlowsImpl,
  GetPositionImpl,
  GetTransactionsImpl,
  ImportBackupImpl,
  InitializeAuthImpl,
  InitializeDatasourceImpl,
  ListRealEstateImpl,
  ObserveAuthStateImpl,
  SignInWithEmailImpl,
  SignInWithGoogleImpl,
  SignOutImpl,
} from "@/application/usecases"

import { DataManager } from "@/services/database/dataManager"

import {
  CloudRegisterAdapter,
  CredentialsRepository,
  CryptoWalletConnectionRepository,
  EntityRepository,
  ExternalEntityRepository,
  LastFetchesRepository,
  PendingFlowRepository,
  PositionRepository,
  RealEstateRepository,
  TransactionRepository,
  VirtualImportRepository,
} from "@/services/database/repositories"

import { AsyncStorageBackupLocalRegistry } from "@/services/backup/backupLocalRegistryStorage"
import { backupClient, backupProcessor } from "@/services/backup"
import { authProvider } from "@/services/auth"
import { AuthPortAdapter } from "@/services/auth/authPortAdapter"
import { AsyncStorageConfigStorage } from "@/services/config/configStorage"

import {
  AsyncStorageExchangeRateStorage,
  CryptoAssetInfoClient,
  ExchangeRateClient,
  MetalPriceClient,
} from "@/services/client/rates"

let container: ApplicationContainer | null = null
let dataManager: DataManager | null = null

const lazy = <T>(factory: () => T): (() => T) => {
  let value: T | undefined
  return () => (value ??= factory())
}

const getDataManagerInstance = (): DataManager => {
  if (!dataManager) {
    dataManager = new DataManager()
  }
  return dataManager
}

export function createApplicationContainer(): ApplicationContainer {
  const dm = getDataManagerInstance()

  const positionRepo = new PositionRepository(dm)
  const transactionRepo = new TransactionRepository(dm)
  const entityRepo = new EntityRepository(dm)
  const lastFetchesRepo = new LastFetchesRepository(dm)
  const realEstateRepo = new RealEstateRepository(dm)
  const pendingFlowRepo = new PendingFlowRepository(dm)
  const credentialsRepo = new CredentialsRepository(dm)
  const externalEntityRepo = new ExternalEntityRepository(dm)
  const cryptoWalletConnectionsRepo = new CryptoWalletConnectionRepository(dm)
  const virtualImportRepo = new VirtualImportRepository(dm)

  const backupLocalRegistry = new AsyncStorageBackupLocalRegistry()
  const cloudRegister = new CloudRegisterAdapter(authProvider)
  const authPort = new AuthPortAdapter(authProvider)
  const configStorage = new AsyncStorageConfigStorage()

  const backupablePorts = new Map<BackupFileType, Backupable>()
  backupablePorts.set(BackupFileType.DATA, dm)
  backupablePorts.set(BackupFileType.CONFIG, configStorage)

  const getPosition: GetPosition = new GetPositionImpl(positionRepo, entityRepo)
  const getTransactions: GetTransactions = new GetTransactionsImpl(
    transactionRepo,
    entityRepo,
  )
  const getAvailableEntities: GetAvailableEntities =
    new GetAvailableEntitiesImpl(
      entityRepo,
      externalEntityRepo,
      credentialsRepo,
      cryptoWalletConnectionsRepo,
      lastFetchesRepo,
      virtualImportRepo,
    )
  const getPendingFlows: GetPendingFlows = new GetPendingFlowsImpl(
    pendingFlowRepo,
  )
  const listRealEstate: ListRealEstate = new ListRealEstateImpl(realEstateRepo)

  const getBackups: GetBackups = new GetBackupsImpl(
    backupablePorts,
    backupClient,
    backupLocalRegistry,
    cloudRegister,
  )

  const initializeDatasource: InitializeDatasource =
    new InitializeDatasourceImpl(dm)
  const checkDatasourceExists: CheckDatasourceExists =
    new CheckDatasourceExistsImpl(dm)

  const clearLocalData: ClearLocalData = new ClearLocalDataImpl(
    dm,
    backupLocalRegistry,
    configStorage,
  )

  const initializeAuth: InitializeAuth = new InitializeAuthImpl(authPort)
  const getAuthSession: GetAuthSession = new GetAuthSessionImpl(authPort)
  const observeAuthState: ObserveAuthState = new ObserveAuthStateImpl(authPort)

  const getDefaultCurrency: GetDefaultCurrency = new GetDefaultCurrencyImpl(
    configStorage,
  )

  const exchangeRateProviderLazy = lazy(() => new ExchangeRateClient())
  const cryptoAssetInfoProviderLazy = lazy(() => new CryptoAssetInfoClient())
  const metalPriceProviderLazy = lazy(() => new MetalPriceClient())
  const exchangeRatesStorageLazy = lazy(
    () => new AsyncStorageExchangeRateStorage(),
  )

  const getExchangeRatesLazy = lazy<GetExchangeRates>(
    () =>
      new GetExchangeRatesImpl(
        exchangeRateProviderLazy(),
        cryptoAssetInfoProviderLazy(),
        metalPriceProviderLazy(),
        exchangeRatesStorageLazy(),
        positionRepo,
      ),
  )

  const importBackupLazy = lazy<ImportBackup>(
    () =>
      new ImportBackupImpl(
        dm,
        backupablePorts,
        backupProcessor,
        backupClient,
        backupLocalRegistry,
        cloudRegister,
      ),
  )

  const getLocalLastUpdateLazy = lazy<GetLocalLastUpdate>(
    () => new GetLocalLastUpdateImpl(dm),
  )

  const signInWithEmailLazy = lazy<SignInWithEmail>(
    () => new SignInWithEmailImpl(authPort),
  )

  const signInWithGoogleLazy = lazy<SignInWithGoogle>(
    () => new SignInWithGoogleImpl(authPort),
  )

  const signOutLazy = lazy<SignOut>(() => new SignOutImpl(authPort))

  const containerBase = {
    getPosition,
    getTransactions,
    getAvailableEntities,
    getPendingFlows,
    listRealEstate,
    getBackups,

    initializeDatasource,
    checkDatasourceExists,
    clearLocalData,

    initializeAuth,
    getAuthSession,
    observeAuthState,

    getDefaultCurrency,
  } as unknown as ApplicationContainer

  Object.defineProperty(containerBase, "importBackup", {
    enumerable: true,
    get: () => importBackupLazy(),
  })

  Object.defineProperty(containerBase, "getLocalLastUpdate", {
    enumerable: true,
    get: () => getLocalLastUpdateLazy(),
  })

  Object.defineProperty(containerBase, "signInWithEmail", {
    enumerable: true,
    get: () => signInWithEmailLazy(),
  })

  Object.defineProperty(containerBase, "signInWithGoogle", {
    enumerable: true,
    get: () => signInWithGoogleLazy(),
  })

  Object.defineProperty(containerBase, "signOut", {
    enumerable: true,
    get: () => signOutLazy(),
  })

  Object.defineProperty(containerBase, "getExchangeRates", {
    enumerable: true,
    get: () => getExchangeRatesLazy(),
  })

  container = containerBase
  return container
}

export function getApplicationContainer(): ApplicationContainer {
  if (!container) {
    throw new Error(
      "Application container not initialized. Call createApplicationContainer first.",
    )
  }
  return container
}

export function getOrCreateApplicationContainer(): ApplicationContainer {
  return container ?? createApplicationContainer()
}

export async function resetApplicationContainer(): Promise<void> {
  container = null
  if (dataManager) {
    const dm = dataManager
    dataManager = null
    await dm.close()
  }
}
