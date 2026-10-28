FROM python:3.13-alpine
WORKDIR /app
COPY tagged_server.py ./
COPY static/ ./static/
EXPOSE 8080
CMD ["python", "-u", "tagged_server.py", "--port", "8080"]
