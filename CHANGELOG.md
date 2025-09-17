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

