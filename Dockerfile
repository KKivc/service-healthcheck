FROM python:3.12

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY healthcheck.py config.json web.py ./
COPY templates/ ./templates/
ENTRYPOINT ["python"]
CMD ["healthcheck.py", "--interval", "60"]