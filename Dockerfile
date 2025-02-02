FROM python:3.9-slim

COPY requirements.txt .
COPY requirements-selenium.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./bank-scraper /bank-scraper
COPY ./resources /bank-scraper/resources

ARG SELENIUM_SUPPORT=true

RUN bash -c 'if [ "$SELENIUM_SUPPORT" = "true" ]; then \
    # Install selenium Python dependencies
    pip install --no-cache-dir -r requirements-selenium.txt && \
    # reCAPTCHA break related dependencies
    apt update && \
    apt install ffmpeg flac curl -y && \
    # Clean up
    apt clean && rm -rf /var/lib/apt/lists/*; \
fi'

WORKDIR /bank-scraper

CMD ["python", "app.py"]