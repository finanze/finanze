// English translations
export const en = {
  common: {
    loading: "Loading...",
    error: "Error",
    retry: "Retry",
    cancel: "Cancel",
    confirm: "Confirm",
    continue: "Continue",
    save: "Save",
    delete: "Delete",
    edit: "Edit",
    close: "Close",
    next: "Next",
    back: "Back",
    done: "Done",
    ok: "OK",
  },

  auth: {
    signIn: "Sign In",
    signUp: "Sign Up",
    signOut: "Sign Out",
    signOutConfirmTitle: "Sign Out",
    signOutConfirmMessage: "Are you sure you want to sign out?",
    email: "Email",
    password: "Password",
    emailPlaceholder: "Enter your email",
    passwordPlaceholder: "Enter your password",
    signInWithGoogle: "Sign in with Google",
    orContinueWith: "or continue with",
    termsNotice:
      "By signing in, you agree to our Terms of Service and Privacy Policy",
    invalidCredentials: "Invalid email or password",
    emailRequired: "Please enter both email and password",
    loggingIn: "Signing in...",
    signingOut: "Signing out...",
    signOutError: "Failed to sign out. Please try again.",
  },

  onboarding: {
    welcomeSubtitle: "Your data is always encrypted",
    noBackupTitle: "No Backup Found",
    noBackupMessage:
      "To use this app, you need to create a backup from the Finanze desktop app first.",
    noBackupInstructions:
      "Open the desktop app, go to Settings > Cloud and make sure you are logged in, then enable backups.",
    openDesktopApp: "I understand",
    decryptData: "Decrypt data",
    importMessage:
      "Enter the password you have used in the Desktop app to sync your data.",
    decryptMessage: "Enter your password to decrypt your financial data.",
    importingBackup: "Importing your data...",
    importingDescription: "Please wait and don't close the app",
    decryptingData: "Decrypting your data...",
    decryptingDescription: "Please wait and don't close the app",
    importSuccess: "Data imported successfully!",
    importError: "Failed to import backup",
    backupTooOld:
      "This backup was created with an older desktop app. Please update the desktop app and make a new backup.",
    backupTooNew:
      "This backup was created with a newer version. Please update the mobile app and try again.",
    wrongPassword: "Incorrect password. Please try again.",
    dataPassword: "Password",
    dataPasswordPlaceholder: "Enter your data password",
    dataPasswordRequired: "Please enter your data password",
    importData: "Import Data",
    notAllowedTitle: "No Cloud Access",
    notAllowedMessage:
      "Your account doesn't have permission to use Finanze Cloud",
    notAllowedHint:
      "Please sign out and use an account with Cloud access, or contact us at finanze.me",
  },

  dashboard: {
    title: "Dashboard",
    welcomeBack: "Welcome back",
    netWorth: "Net Worth",
    assetDistribution: "By Asset",
    entityDistribution: "By Entity",
    recentTransactions: "Recent Transactions",
    ongoingInvestments: "Ongoing Investments",
    noData: "No data available",
    noTransactions: "No transactions yet",
    noInvestments: "No ongoing investments",
    pullToRefresh: "Pull to refresh",
    daysLeft: "d left",
    daysDelay: "d delay",

    includePendingMoney: "Include pending money",
    includeCardExpenses: "Include card pending expenses",
    includeRealEstateEquity: "Include real estate equity",
    includeResidences: "Include residences",
  },

  settings: {
    title: "Settings",
    account: "Account",
    signedInAs: "Signed in as",
    appVersion: "Finanze {version}",
    language: "Language",
    languageEnglish: "English",
    languageSpanish: "Spanish",
    theme: "Theme",
    themeLight: "Light",
    themeDark: "Dark",
    themeSystem: "System",
    about: "About",
    hideAmounts: "Hide amounts",

    general: "General",
    defaultCurrency: "Default currency",
    appearance: "Appearance",
    data: "Data",
    noDataLoaded: "No data loaded",
    importBackup: "Import Backup",
    lastSync: "Last sync",
    deleteDataTitle: "Delete Data",
    deleteDataMessage:
      "Are you sure you want to delete all data? This cannot be undone.",
    deleteLocalData: "Delete local data",
    deleteDataError: "Failed to delete data",
  },

  assets: {
    CASH: "Cash",
    ACCOUNT: "Cash",
    FUND: "Funds",
    STOCK_ETF: "Stocks & ETFs",
    DEPOSIT: "Deposits",
    REAL_ESTATE_CF: "Real Estate CF",
    REAL_ESTATE: "Real Estate",
    FACTORING: "Factoring",
    CROWDLENDING: "Crowdlending",
    CRYPTO: "Crypto",
    COMMODITY: "Commodities",
    BOND: "Bonds",
    DERIVATIVE: "Derivatives",
    LOAN: "Loans",
    CARD: "Cards",
    FUND_PORTFOLIO: "Fund Portfolio",
    PENDING_FLOWS: "Pending",
  },

  entities: {
    REAL_ESTATE: "Real Estate",
    COMMODITY: "Commodities",
    CRYPTO: "Crypto",
  },

  investments: {
    amount: "Amount",
    return: "Return",
    maturity: "Maturity",
    DEPOSIT: "Deposit",
    REAL_ESTATE_CF: "Real Estate",
    FACTORING: "Factoring",
    CROWDLENDING: "Crowdlending",
  },

  errors: {
    networkError: "Network error. Please check your connection.",
    serverError: "Server error. Please try again later.",
    unexpectedError: "An unexpected error occurred.",
    tooManyRequests: "Too many requests. Please try again later.",
  },
}

export type Translations = typeof en
