## [0.8.0] - 2026-04-23

### 🚀 Features

- Add cloud backup system (WIP, closed access) 
- Add manual cryptos input (#71)
- Add mobile application adapting existing base with Pyodide+Capacitor, not all features available but most of them
- Use different MyInvestor client ids
- Add better instrument data fetching sources and backups
- Add xpub support for BTC and LTC (#73)
- Add DEGIRO integration (#74)
- Improve per asset position donut charts, compact number format option & asset sorting (#76)
- Improve asset list UI
- Add instrument icons, stored issuer and captcha handling
- Handle DEGIRO maintenance mode with proper error message (#78)
- Add IBKR integration (#79)
- Add binance, derivatives, multiaccount support for crypto exchanges & mobile manual entity login (#82)
- Loan linkage in real estate, more loan parameters, manual loan auto update & couple manual position bugs (#83)
- Add euribor suggestions (#84)
- Improve entity selector, contribution chart improvement and filtering, money flows grouping, loans dashboard option and related minor UI improvements (#85)
- Add credit line support (#88)
- Add privacy mode, derived wallet individual addresses and balances and manual edit flow improvement (#89)

### 🐛 Bug Fixes

- User creation await (#75)
- Add @property decorator to KnownIssuer.compact to fix TypeError in _match_issuer
- Real estate mortgage input, fetching keys handling & ING connection (#81)
- Pending money not properly showing in forecast, real estate taxes option in forecas, minor real estate cf fixes & input improvements (#86)
- Cloud session closure (#91)
- Improve windows icon, enable auto update for mac & stabilize frontend dockerfile build

### 💼 Other

- Improve query management

### 📚 Documentation

- Fix image

### ⚙️ Miscellaneous Tasks

- GH Workflows updates
- Update to Python 3.14
- Polishing mobile app (#87)
- Add macos notarization & ios apple sign in (#90)
## [0.7.0] - 2025-12-07

### 🚀 Features

- Add multiple addresses at once feature
- Add MyInvestor pension plan funds
- Add contribution target subtypes (mutual fund, private equity, pension plan, etc) and minor MyInvestor fetch improvements
- Add rate/price storage to avoid third party providers outage errors
- Pinnable money management pages and more info in recurring money page
- Crypto redesign with improved asset view and limitless token support within supported networks
- Add ING broker portfolio support (stocks & ETFs)
- Etherscan integration no longer required to connect BSC & new hide unknown tokens option to avoid fake tokens
- Improve external integration system & add integration disconnection
- Add Cajamar support (global position: accounts, cards & loans)
- Add application specific settings and move settings tab
- Improve logging and add log storage
- Add Ethplorer API for ETH and BSC
- Moved all export and import features to a single page, to allow configuring and use it from a single point
- New export & import template based system (breaking)
- Add file export and import from & to CSV, TSV and Excel
- Improved crypto exchange rate with contract addresses
- Advanced backend server configuration (logs & external server config)
- Improved profitability calculation, remade SEGO factoring transaction handling (deep fetch required), add factoring late interest rate and historic fixes
- Redesign transactions view and added calendar view, redesigned upcoming money events loading
- Add money events calendar and improve overall animations
- Support TradeRepublic crypto natively and add crypto periodic contributions
- Add Auto Refresh to automatically update entity data if possible
- Show compatible entity products in integrations
- Add savings calculator with retirement support, multi scenarios and more
- Allow pin input from refresh dropdown, improve MyInvestor asset currency handling, Urbanitae annual interest fetch and TR account interest temporarily unavailable
- Add simultaneous entity fetch

### 🐛 Bug Fixes

- Export not exporting all data & improve overall entity loading
- Minor real estate UI enhacements
- Handle multiple security accounts in MyInvestor
- Keep window position, MyInvestor origin currencies and minor improvements

### 📚 Documentation

- Update README and screenshots

### ⚙️ Miscellaneous Tasks

- Packaging updates to boost startup time & auto updates (alpha)
- Docker dev versioning
- Github Workflow improvements
## [0.6.0] - 2025-10-26

### 🚀 Features

- Manual transactions, asset position and contributions (#56)
- Add money market fund asset type
- Improve initial investment Real Estate calculation in dashboard KPIs
- Show warning when first or deep transaction fetch
- Improve asset details and state translations
- Use MyInvestor original transfer initial investment
- Partial fetch for all-crypto fetch
- Add fund KIID link
- Improve fetch cooldown management and extended for crypto
- Add real estate CF and factoring investment historic
- Improve entity login, fetching, pin entering UI and minor entity integrations page fixes
- Add about section and improve migration handling/info
- Add instrument search and data helper when manual adding
- Add more fund/etf/stock backing sources & price tracker to keep manual positions up to date
- Show extended maturity in real estate cf
- Add private equity and pension fund tx support
- Add private markets trade republic support (not stable)
- Improve exchange rates loading
- Check database version is not ahead

### 🐛 Bug Fixes

- V0601 table migration
- Overlay expanded sidebar in narrow view
- ING web app not saving session properly
- Multifetch for Bitcoin allowing much more addresses at once & add request cooldowns to crypto fetchers
- Migrate database stock equity types
- Improved general loading, general error messages and minor UI fixes
- General database transaction management fixes, theme application, login handling improvements and login options

### ⚙️ Miscellaneous Tasks

- Update frontend dependencies
- Improve development release versioning
## [0.5.2] - 2025-10-13

### 🐛 Bug Fixes

- MyInvestor API patch
## [0.5.1] - 2025-09-27

### 🚀 Features

- Add account retained balance support for ING
- Improve GoCardless instructions
- Improve investment data presentation with new my asset page and per asset pinning
- Add MyInvestor support for standard funds
- Add commodities asset page

### 🐛 Bug Fixes

- Not showing previously disconnected external entities
- Initial system theme load from browser
- Skip accounts without currency or balance and fallback to balance currency
- Trade Republic position fetch trying to get fund details for all asset types
- Trade Republic failing when only found unknown asset type periodic contributions & prioritize first balance in GoCardless account info
## [0.5.0] - 2025-09-17

### 🚀 Features

- Add Unicaja fund periodic contribution
- Add ING support (accounts, cards and broker txs)
- Add GoCardless integration to increase financial institution variety
- Add Indexa Capital transaction support, add fee support also in MyInvestor, improve fund details sections and minor portfolio/fund related fixes
- Add ING fund position, transactions and periodic contributions
- Add Trade Republic mutual funds
- Add commodities price timeout
- Improve earnings and expenses data visualization
- Show automatic contributions overview in recurring money page
- Add fund asset type details and distribution (MyInvestor, TR & Indexa Capital)
- Show last data fetch when selecting features to fetch

### 🐛 Bug Fixes

- Migration error
## [0.4.1] - 2025-09-05

### 🐛 Bug Fixes

- Unicaja login
## [0.4.0] - 2025-08-29

### 🚀 Features

- Earnings and expenses
- Add year picker to date picker
- Asset navigation shortcut from dashboard
- Add pending money barcharts
- Add real estate support, advanced related investment KPIs and linked money flows
- Minor improvements in entity data fetch process
- Add entity contributions page and dashboard integration
- Improve investment asset detail pages data and distribution
- Add position forecast feature
- Add pin pad keyboard support and minor improvements

### 🐛 Bug Fixes

- Minor earnings and expenses display improvements
# Changelog

All notable changes to this project will be documented in this file.

## [0.3.0] - 2025-07-23

### 🚀 Features

- Add data importing error information
- Add external integrations, google sheets
- Add entity external integrations, etherscan and BSC support
- Show export sheet not found errors
- Add export option to exclude imported/manual data
- Add version release notification
- Improve sidebar button display
- Add password change feature
- Add banking dashboard with account, cards and loans detailed info and KPIs

### 🐛 Bug Fixes

- Add product type field validation
- Empty virtual fetch causing error and unknown error handling in import
- Historic real estate name
- Improve integration requirement warnings
- Export empty asset table not emptying previously filled table
- Wecity balance and use pending amount for totals

### 📚 Documentation

- Update macOS instructions
- Update crypto related feats

## [0.2.0] - 2025-07-10

### 🚀 Features

- Add crypto wallet integration, muticurrency suppor, improved export, config versioning and entity data fetch renaming (#34)
- Improve settings data type selection, improve dashboard view, fix icons, improve entity card viewsa and improve data fetch
- Improved fetching date register, dashboard detailed asset visuals and minor fixes
- Improved exporting and importing (allow account, card, loan and portfolio import/export) and related settings UI
- Add transactions view
- Transactions improvements in fitlering and info
- Add commodity support, market value tracking, weight conversions and related profitability
- Crowdlending import/export
- Use dough chart
- Dashboards per asset type
- Deep fetch now clears all existing transactions

### 🐛 Bug Fixes

- Virtual import not available in integration page if not setup, and default date format in export/import
- Don't show deep fetch option if no transactions feature is available
- Total assets calculation & sheets integration status
- Mispelled translations

### 💼 Other

- Cleaned and renamed internal enums

### 📚 Documentation

- Update images

### ⚙️ Miscellaneous Tasks

- Add macos x86 build
- Fix release workflow

## [0.1.2] - 2025-06-18

### 🐛 Bug Fixes

- Wecity interest txs, show net in txs in front and fix features not being selected when 2FA

## [0.1.1] - 2025-06-15

### 🚀 Features

- Exclude disconnected entities only
- Store default currency in config (not user visible yet)
- Single execution for critical use cases
- Improve virtual import and filter old imported positions
- Add deep fetch
- Add by entity distribution in dashboard

### 🐛 Bug Fixes

- Dashboard txs shown for connected entities and improved value displaying
- Operlaping dashboard chart
- Dashboard autoreload on entity fetch, texts and sidebar centering
- Toast visibility

### 📚 Documentation

- Add some captures

## [0.1.0] - 2025-06-13

### 🚀 Features

- Add full stack finanze
- Update Windows titlebar, system theme mode and proper quit
- Add google sheets credentials input & improved server credential load
- Add user profile support, signup view and endpoint
- Use api rest for ucaja loans

### 🐛 Bug Fixes

- Ci workflows
- Improve packaging

### 📚 Documentation

- Update google sheets env vars
- Update readme

### ⚙️ Miscellaneous Tasks

- Add lint hook in front
- Improved hooks and python lint
- Fix create release wf

