#!/bin/sh

START_WAIT_TIME=${START_WAIT_TIME_SECONDS:-60}
WAIT_TIME=${WAIT_TIME_SECONDS:-7200}

# Initially wait for 30 seconds
sleep "$START_WAIT_TIME"

while true; do
  # Call for MY_INVESTOR
  curl -X POST http://bank-scraper:8080/api/v1/scrape \
    -H 'Content-Type: application/json' \
    -d '{"bank": "MY_INVESTOR"}'

  # Call for UNICAJA
  curl -X POST http://bank-scraper:8080/api/v1/scrape \
    -H 'Content-Type: application/json' \
    -d '{"bank": "UNICAJA"}'

  # Update Google Sheets
  curl -X POST http://bank-scraper:8080/api/v1/update-sheets;

  # Wait for 1 hour
  sleep "$WAIT_TIME"
done
