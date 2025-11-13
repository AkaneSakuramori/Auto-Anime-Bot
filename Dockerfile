FROM python:3.10-slim-bullseye
WORKDIR /usr/src/app
RUN chmod 777 /usr/src/app

RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    git wget pv jq python3-dev mediainfo gcc \
    libsm6 libxext6 libfontconfig1 libxrender1 libgl1-mesa-glx && \
    rm -rf /var/lib/apt/lists/*

COPY --from=mwader/static-ffmpeg:6.1 /ffmpeg /bin/ffmpeg
COPY --from=mwader/static-ffmpeg:6.1 /ffprobe /bin/ffprobe

# Install lxml dependencies first
RUN pip3 install --no-cache-dir lxml lxml_html_clean

COPY . .
RUN pip3 install --no-cache-dir -r requirements.txt

# Expose port for health checks
EXPOSE 8080

CMD ["bash","run.sh"]
