FROM python:3.9-slim

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./bank-scraper /bank-scraper
COPY ./resources /bank-scraper/resources

ARG INCLUDE_FIREFOX=true

RUN if [ "$INSTALL_FIREFOX" = "true" ]; then \
    # Firefox
    apt install firefox-esr openssl -y && \
    # Geckodriver into /usr/local/bin/
    apt install wget -y && \
    wget -qO /tmp/geckodriver.tar.gz \
    "https://github.com/mozilla/geckodriver/releases/download/v0.35.0/geckodriver-v0.35.0-linux-aarch64.tar.gz" && \
    tar -xzf /tmp/geckodriver.tar.gz -C /usr/local/bin/ && \
    rm /tmp/geckodriver.tar.gz && \
    apt remove -y wget && apt clean && rm -rf /var/lib/apt/lists/*; \
fi

ENV GECKODRIVER_PATH=/usr/local/bin/geckodriver

WORKDIR /bank-scraper

CMD ["python", "app.py"]