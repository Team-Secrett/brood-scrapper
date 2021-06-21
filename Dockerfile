FROM docker.uclv.cu/python:3.8.5

WORKDIR /app

COPY requirements.txt /app

RUN pip install --no-cache-dir -r requirements.txt
        #--index-url http://nexus.prod.uci.cu/repository/pypi-proxy/simple/ \
        #--trusted-host nexus.prod.uci.cu

COPY . .
