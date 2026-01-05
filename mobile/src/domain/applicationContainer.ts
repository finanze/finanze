import type {
  GetPosition,
  GetTransactions,
  GetAvailableEntities,
  GetPendingFlows,
  ListRealEstate,
  GetBackups,
  ImportBackup,
  InitializeDatasource,
  CheckDatasourceExists,
  ClearLocalData,
  GetLocalLastUpdate,
  InitializeAuth,
  GetAuthSession,
  ObserveAuthState,
  SignInWithEmail,
  SignInWithGoogle,
  SignOut,
  GetDefaultCurrency,
  GetExchangeRates,
} from "@/domain/usecases"

export interface ApplicationContainer {
  getPosition: GetPosition
  getTransactions: GetTransactions
  getAvailableEntities: GetAvailableEntities
  getPendingFlows: GetPendingFlows
  listRealEstate: ListRealEstate
  getBackups: GetBackups
  importBackup: ImportBackup

  initializeDatasource: InitializeDatasource
  checkDatasourceExists: CheckDatasourceExists

  clearLocalData: ClearLocalData
  getLocalLastUpdate: GetLocalLastUpdate

  initializeAuth: InitializeAuth
  getAuthSession: GetAuthSession
  observeAuthState: ObserveAuthState
  signInWithEmail: SignInWithEmail
  signInWithGoogle: SignInWithGoogle
  signOut: SignOut

  getDefaultCurrency: GetDefaultCurrency

  getExchangeRates: GetExchangeRates
}
