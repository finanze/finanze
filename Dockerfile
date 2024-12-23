FROM python:3.9-slim

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./bank-scraper /bank-scraper
COPY ./resources /bank-scraper/resources

# Firefox
# RUN apt install firefox-esr -y
# RUN apt install openssl -y

# ENV GECKODRIVER_PATH=/usr/local/bin/geckodriver

# Geckodriver into /usr/local/bin/
# RUN apt install wget -y
# RUN wget -qO /tmp/geckodriver.tar.gz \
#     "https://github.com/mozilla/geckodriver/releases/download/v0.35.0/geckodriver-v0.35.0-linux-aarch64.tar.gz" \
#     && tar -xzf /tmp/geckodriver.tar.gz -C /usr/local/bin/ \
#     && rm /tmp/geckodriver.tar.gz
# RUN apt remove wget -y

WORKDIR /bank-scraper

CMD ["python", "app.py"]