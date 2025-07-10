# Changelog

All notable changes to this project will be documented in this file.

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

