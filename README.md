# Bank Scraper

This is a Python-based application designed to aggregate financial data from various banking and investment
platforms. It supports multiple entities and features, providing a unified interface to gather and process financial
information.

Not actively maintained as it was meant only for personal use, so some banks/entities/features/instruments may not
work, be outdated or partially implemented.

## Table of Contents

- [Features](#features)
- [Setup](#setup)
- [Configuration](#configuration)
- [Environment Variables](#environment-variables)
- [Usage](#usage)
- [Credits](#credits)

## Features

- Scrape financial data from multiple entities
- Support for various financial products (stocks, funds, real estate crowdfunding, etc.)
- Dynamic and customizable data export to Google Sheets
- Virtual scraping for simulated data

### Supported Assets by Entity

| Entity         | Accounts | Cards | Funds | Stock/<br>ETFs | Deposits | Portfolios | Loans/<br>Mortgages | Crypto | Bonds | Specific            |
|----------------|----------|-------|-------|----------------|----------|------------|---------------------|--------|-------|---------------------|
| Urbanitae      | ✅        | -     | -     | -              | -        | -          | -                   | -      | -     | Lending Investments |
| MyInvestor     | ✅        | ✅     | ✅     | ✅              | ✅        | WIP        | ❌                   | -      | -     |                     |
| SEGO           | ✅        | -     | -     | -              | -        | -          | -                   | -      | -     | Factoring           |
| Trade Republic | ✅        | -     | -     | ✅              | -        | -          | -                   | ✅      | ❌     |                     |
| Unicaja        | ✅        | ✅     | ❌     | ❌              | ❌        | -          | ✅                   | -      | -     |                     |
| Wecity         | ✅        | -     | -     | -              | -        | -          | -                   | -      | -     | Investments         |
| Mintos         | ✅        | -     | -     | ❌              | ❌        | -          | -                   | -      | ❌     | Crowdlending        |
| Freedom24      | ✅        | -     | -     | ❌              | ✅        | -          | -                   | -      | ❌     |                     |

### Entity Features

Not all entities support the same features, in general we can group data in the following categories:

- **Global Position**: current financial position including the current state of assets mentioned above, this is
  supported by all entities.
- **Periodic Contributions**: automatic periodic contributions made to investments such as Funds (MyInvestor) or
  Stocks/ETFs (Trade Republic).
- **Transactions**: all the account/investment related transactions, interest payments, stock of fund operations, asset
  maturity... (deposits are not included here)
- **Investment Historic**: aggregates past positions and TXs to create a history of past and current investments.

| Entity         | Global Position | Periodic<br>Contributions | Transactions | Investment<br>Historic |
|----------------|-----------------|---------------------------|--------------|------------------------|
| Urbanitae      | ✅               | -                         | ✅            | ✅                      |
| MyInvestor     | ✅               | ✅                         | ✅            | ❌                      |
| SEGO           | ✅               | -                         | ✅            | ✅                      |
| Trade Republic | ✅               | WIP                       | ✅            | -                      |
| Unicaja        | ✅               | -                         | ❌            | -                      |
| Wecity         | ✅               | -                         | ✅            | ✅                      |
| Mintos         | ✅               | -                         | ❌            | ❌                      |
| Freedom24      | ✅               | -                         | ❌            | ❌                      |

### Entity notes

Some entities require a 2FA to login or get its data, which doesn't allow to background update, this applies to the
following ones:

- **SEGO** (e-mail)
- **Trade Republic** (mobile app)
- **Wecity** (SMS)

Important points to remark:

- **Unicaja** at the moment requires setting `UNICAJA_ABCK` environment variable to login, as it uses Akamai for anti
  bot
  protection, good news is that it last for a year approx.
- **Mintos** is experimental, as it needs Selenium to resolve reCAPTCHA,
  checkout [docker-compose.yml](docker-compose.yml).

### Google Sheets export

This project allows to create complex dashboards and tables in Google Sheets, aggregating and formatting the scraped
data. Check [Export & Import Configuration](#export--import-configuration) for more info.

## Setup

### Docker

Two Docker images are available, a Selenium one and a light one (ex-selenium). The first one is the default, which
currently is
needed for Mintos, as it contains Selenium and reCAPTCHA resolution related Python and SO dependencies (like ffmpeg).

Both are available at Docker Hub [marcosav/bank-scraper](https://hub.docker.com/r/marcosav/bank-scraper).

A very basic front end is available just to handle login, data retrieval and export.
at [marcosav/bank-scraper-front](https://hub.docker.com/r/marcosav/bank-scraper-front).

### Development

This project requires `Python 3.11`.

1. Clone the repository:
    ```sh
    git clone https://github.com/marcosav/bank-scraper.git
    cd bank-scraper
    ```

2. Create a virtual environment and activate it (recommended Pyenv):
    ```sh
    python3 -m venv venv
    source venv/bin/activate
    ```

3. Install the required dependencies:
    ```sh
    pip install -r requirements.txt
    pip install -r requirements-selenium.txt  # If you want to use Selenium for reCAPTCHA
    ```

## Export & Import Configuration

Checkout the default [template_config.yml](resources/template_config.yml) config that will be created on first start,
which contains some examples of tables and summary dashboards.

## Environment Variables

Checkout example docker-compose.yml for the environment variables that can be used to override the default config, most
important ones are::

- **Mandatory** `DB_CIPHER_PASSWORD` for DB encryption passphrase
- `GOOGLE_` prefixed ones, needed for Google credentials, in case of using import/export to Google Sheets
- Other Selenium related ones.

## Credentials

There are two ways of handling this, the default and recommended one is storing them in the encrypted database,
this is done using the login endpoint showed in the [Usage](#usage) section. This mode is enabled by default.

Credentials can also be stored in the environment variables like `{ENTITY_NAME}_USERNAME` and `{ENTITY_NAME}_PASSWORD`.
Except for `MYI_USERNAME` and `MYI_PASSWORD` in MyInvestor case, and `TR_PHONE` and `TR_PIN` for Trade Republic.
This is enabled by setting `CREDENTIAL_STORAGE` environment variable to `ENV`.

Also, credentials_reader.py is a basic and unsecure implementation to retrieve credentials from environments, there you
can get the needed environment names.

## Usage

1. Start the application:
    ```sh
    python app.py
    ```

2. Use the provided API endpoints to interact with the scraper:
    - `GET /api/v1/scrape`: Get available entities.
    - `POST /api/v1/entity/login`: Login to a specific entity.
   ```
   {
        "entity": "e0000000-0000-0000-0000-000000000001",    // MyInvestor
        "credentials": {                                     // Credentials object schema defined
            "user": "12345678G",                             // by "credentials_template" field
            "password": "MySecretor123"                      // in the available entities endpoint 
        },
        "code": "0000",                                      // Only if 2FA is needed
        "processId": "xxxxxxxxxxx"                           // Same
    }
   ```
    - `POST /api/v1/scrape`: Start a scraping process for a specific entity, this endpoint will also prompt for the
      needed 2FA code if the entity requires it. It will return all scraped data. Resembles the previous one.
   ```
   {
        "entity": "e0000000-0000-0000-0000-000000000003", // Trade Republic
        "features": ["POSITION", "TRANSACTIONS"],
        "code": "0000",                              // Only if 2FA is needed
        "processId": "xxxxxxxxxxx",                  // Same
        "avoidNewLogin": false,                      // Avoid new login if session has expired and 2FA is required (optional, defaults to false)
    }
   ```
    - `POST /api/v1/update-sheets`: Update Google Sheets with the latest data.
    - `POST /api/v1/scrape/virtual`: Perform a virtual scrape.

## Credits

- Selenium reCAPTCHA resolution is based
  on [sarperavci/GoogleRecaptchaBypass](https://github.com/sarperavci/GoogleRecaptchaBypass/tree/selenium)
  project, using a slightly modified version of Selenium version. In an attempt of using Playwright I made an adaptation
  for
  it [here](bank-scraper/infrastructure/scrapers/mintos/recaptcha_solver_playwright.py), it works, but has some troubles
  with headless mode.
- Trade Republic client is based on project [pytr-org/pytr](https://github.com/pytr-org/pytr), although it has been
  heavily
  modified to allow resumable sessions, some extra data, fetch non-repeatable transactions and other minor changes, this
  library has been vital for this
  project.
- SQLCipher pre-built dependency [rotki/pysqlcipher3](https://github.com/rotki)