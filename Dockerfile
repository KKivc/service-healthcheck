FROM python:3.12

WORKDIR ./app
COPY healthcheck.py config.json ./
RUN pip install requests
ENTRYPOINT ["python", "healthcheck.py"]
CMD ["--interval", "60"]