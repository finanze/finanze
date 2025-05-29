<p align="center"><img src="frontend/app/public/finanze.png" alt="Finanze Logo" width="220px"></p>
<h1 align="center">Finanze</h1>

<p align="center">
An application designed to aggregate financial data from various banking and investment
platforms. It supports multiple entities and features, providing a unified interface to gather and process financial
information.
</p>

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
| MyInvestor     | ✅        | ✅     | ✅     | ✅              | ✅        | ✅          | ❌                   | -      | -     |                     |
| SEGO           | ✅        | -     | -     | -              | -        | -          | -                   | -      | -     | Factoring           |
| Trade Republic | ✅        | -     | -     | ✅              | -        | -          | -                   | ✅      | ❌     |                     |
| Unicaja        | ✅        | ✅     | ❌     | ❌              | ❌        | -          | ✅                   | -      | -     |                     |
| Wecity         | ✅        | -     | -     | -              | -        | -          | -                   | -      | -     | Investments         |
| Mintos         | ✅        | -     | -     | ❌              | ❌        | -          | -                   | -      | ❌     | Crowdlending        |
| Freedom24      | ✅        | -     | -     | ❌              | -        | -          | -                   | ❌      | ❌     |                     |
| Indexa Capital | ✅⚠️      | -     | ✅⚠️   | -              | -        | ✅⚠️        | -                   | -      | -     |                     |

⚠️ = Not tested

### Entity Features

Not all entities support the same features, in general we can group data in the following categories:

- **Global Position**: current financial position including the current state of assets mentioned above, this is
  supported by all entities.
- **Periodic Contributions**: automatic periodic contributions made to investments such as Funds (MyInvestor) or
  Stocks/ETFs (Trade Republic).
- **Transactions**: all the account/investment related transactions, interest payments, stock of fund operations, asset
  maturity...
- **Investment Historic**: aggregates past positions and TXs to create a history of past and current investments (
  deposits are not included here).

| Entity         | Global Position | Periodic<br>Contributions | Transactions<br>(inv. related) | Investment<br>Historic |
|----------------|-----------------|---------------------------|--------------------------------|------------------------|
| Urbanitae      | ✅               | -                         | ✅                              | ✅                      |
| MyInvestor     | ✅               | ✅                         | ✅                              | ❌                      |
| SEGO           | ✅               | -                         | ✅                              | ✅                      |
| Trade Republic | ✅               | ✅                         | ✅                              | -                      |
| Unicaja        | ✅               | -                         | -                              | -                      |
| Wecity         | ✅               | -                         | ✅                              | ✅                      |
| Mintos         | ✅               | -                         | ❌                              | ❌                      |
| Freedom24      | ✅               | -                         | ✅                              | ❌                      |
| Indexa Capital | ✅⚠️             | -                         | ❌                              | -                      |

### Entity notes

Some entities require a 2FA to login or get its data, which doesn't allow to background update, this applies to the
following ones:

- **SEGO** (e-mail)
- **Trade Republic** (mobile app)
- **Wecity** (SMS)

Important points to remark:

- **Unicaja** requires setting `UNICAJA_ABCK` environment variable to login, as it uses Akamai for anti
  bot protection, good news is that it last for a year approx, if you use front to log in you have nothing to worry
  about.
- **Mintos** needs Selenium to resolve reCAPTCHA when not using frontend.
- **Indexa Capital** is not tested, as I don't have an account.
- **Freedom24** D-Account interest (swaps) txs were supported and its related transactions, but not anymore since its
  removal.

### Google Sheets export

This project allows to create complex dashboards and tables in Google Sheets, aggregating and formatting the scraped
data. Check [Export & Import Configuration](#export--import-configuration) for more info.

## Setup

### Docker

Two Docker images are available, a Selenium one (latest-selenium) and a light one (latest-no-selenium). The first one is
the default, which currently is
needed for Mintos, as it contains Selenium and reCAPTCHA resolution related Python and SO dependencies (like ffmpeg).

Both are available at Docker Hub [marcosav/finanze](https://hub.docker.com/r/marcosav/finanze).

A very basic front end is available just to handle login, data retrieval and export.
at [marcosav/bank-scraper-front](https://hub.docker.com/r/marcosav/bank-scraper-front).

### Development

This project requires `Python 3.11`.

1. Clone the repository:
    ```sh
    git clone https://github.com/marcosav/finanze.git
    cd finanze
    ```

2. Create a virtual environment and activate it (recommended Pyenv for version management):
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

Checking [example_config.yml](resources/example_config.yml) could be useful in order to see some examples of export
tables
and summary dashboards.

## Environment Variables

Checkout example docker-compose.yml for the environment variables that can be used to override the default config, most
important ones are::

- `DB_CIPHER_PASSWORD` for DB encryption passphrase, optional, provided via API (see below).
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
    - `GET /api/v1/login`: Get current user session status.
    - `POST /api/v1/logout`: Exit and lock current session.
    - `POST /api/v1/login`: Login and unlock database.
    - `GET /api/v1/entities`: Get available entities.
   ```
   {
        "password": "xxxxxxxxxxx"
   }
   ```
    - `POST /api/v1/entities/login`: Login to a specific entity.
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
    - `DELETE /api/v1/entities/login`: Disconnect/logout from a specific entity.
   ```
   {
      "id": "e0000000-0000-0000-0000-000000000001"
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
    - `POST /api/v1/export`: Export data (currently only Google Sheets available).
   ```
   {
        "target": "GOOGLE_SHEETS"
   }
   ```
    - `POST /api/v1/scrape/virtual`: Perform a virtual scrape.

## Credits

- Selenium reCAPTCHA resolution is based
  on [sarperavci/GoogleRecaptchaBypass](https://github.com/sarperavci/GoogleRecaptchaBypass/tree/selenium)
  project, using a slightly modified version of Selenium version. In an attempt of using Playwright I made an adaptation
  for
  it [here](finanze/infrastructure/scrapers/mintos/recaptcha_solver_playwright.py), it works, but has some troubles
  with headless mode.
- Trade Republic client is based on project [pytr-org/pytr](https://github.com/pytr-org/pytr), although it has been
  heavily
  modified to allow resumable sessions, some extra data, fetch non-repeatable transactions and other minor changes, this
  library has been vital for this
  project.
- SQLCipher pre-built dependency [rotki/pysqlcipher3](https://github.com/rotki)