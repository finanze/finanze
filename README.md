# Bank Scraper

This is a Python-based application designed to scrape financial data from various banking and investment
platforms. It supports multiple entities and features, providing a unified interface to gather and process financial
information.

This is not actively maintained and was meant only for personal use, so some banks/entities/features/instruments may not
work, be outdated or partially implemented. That's why this documentation is so scarce.

## Table of Contents

- [Features](#features)
- [Setup](#setup)
- [Configuration](#configuration)
- [Environment Variables](#environment-variables)
- [Usage](#usage)
- [Credits](#credits)

## Features

- Scrape financial data from multiple entities
- Support for various financial products (stocks, funds, real estate, etc.)
- Dynamic and customizable data export to Google Sheets
- Virtual scraping for simulated data

### Supported Entities

- `URBANITAE` (wallet & investments)
- `MY_INVESTOR` (periodic automatic fund contributions, funds, stocks/ETFs, main account position & related cards)
- `SEGO` (wallet & factoring)
- `TRADE_REPUBLIC` (stocks/ETFs/Crypto & account) [requires 2FA]
- `UNICJA` (main account and related cards & mortgage)
    - As web login uses Akamai bot protection, setting `UNICAJA_ABCK` is needed.
- `WECITY` (wallet & investments) [requires 2FA]
- `MINTOS` (wallet & loan distribution) (experimental)
    - Needs Selenium to resolve reCAPTCHA, checkout [docker-compose.yml](docker-compose.yml).
- `F24` (savings and brokerage account & deposits)

### Entity Features

Not all entities support the same features. Some or all of the following features are available for each entity:

- `POSITION`: Fetch the current financial position.
- `AUTO_CONTRIBUTIONS`: Fetch the auto-contributions of the entity.
- `TRANSACTIONS`: Fetches all the account/investment transactions.
- `HISTORIC`: Aggregates past positions and txs to create a history of past and current investments.

### Google Sheets export

This project allows to create complex dashboards and tables in Google Sheets, aggregating and formatting the scraped
data. Check [Export & Import Configuration](#export--import-configuration) for more info.

## Setup

### Docker

Two docker images are available, a Selenium one and a light one (ex-selenium). The first one is the default, which
currently is
needed for Mintos, as it contains Selenium and reCAPTCHA resolution related Python and SO dependencies (like ffmpeg).

Both are available at Docker Hub [marcosav/bank-scraper](https://hub.docker.com/r/marcosav/bank-scraper).

A very basic front end is available
at [marcosav/bank-scraper-front](https://hub.docker.com/r/marcosav/bank-scraper-front).

### Development

1. Clone the repository:
    ```sh
    git clone https://github.com/marcosav/bank-scraper.git
    cd bank-scraper
    ```

2. Create a virtual environment and activate it:
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

Checkout example docker-compose.yml for the environment variables that can be used to override the default config, set
Mongo connection related stuff, Google credentials, entity session caches...

Credentials are stored in the environment variables `{ENTITY_NAME}_USERNAME` and `{ENTITY_NAME}_PASSWORD`.
Except for `MYI_USERNAME` and `MYI_PASSWORD` in MyInvestor case, and `TR_PHONE` and `TR_PIN` for Trade Republic.

Also, credentials_reader.py is a basic and unsecure implementation to retrieve credentials from environments, there you
can get the needed environment names.

## Usage

1. Start the application:
    ```sh
    python app.py
    ```

2. Use the provided API endpoints to interact with the scraper:
    - `GET /api/v1/scrape`: Get available entities.
    - `POST /api/v1/scrape`: Start a scraping process for a specific entity, this endpoint will also prompt for the
      needed 2FA code if the entity requires it. It will return all scraped data.
   ```
   {
        "entity": "TRADE_REPUBLIC",
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
  modified to allow resumable sessions, fetch transactions and other minor changes, this library has been vital for this
  project.