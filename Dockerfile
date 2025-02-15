FROM python:3.10-slim

# Install system dependencies including wkhtmltopdf and its dependencies
RUN apt-get update && apt-get install -y \
    wkhtmltopdf \
    xvfb \
    xfonts-75dpi \
    xfonts-base \
    fontconfig \
    libjpeg62-turbo \
    libxrender1 \
    wget \
    && rm -rf /var/lib/apt/lists/*

# # Create a wrapper script for wkhtmltopdf with xvfb
# RUN echo '#!/bin/bash\nxvfb-run -a --server-args="-screen 0, 1024x768x24" /usr/bin/wkhtmltopdf $*' > /usr/local/bin/wkhtmltopdf.sh \
#     && chmod +x /usr/local/bin/wkhtmltopdf.sh

WORKDIR /flask-app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "9", "app:app"]