ARG BUILD_FROM
FROM ${BUILD_FROM}

WORKDIR /app

COPY edge/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY edge/src/ /app/edge/src/
RUN touch /app/edge/__init__.py && mkdir -p /data

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
