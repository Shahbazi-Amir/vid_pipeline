FROM python:3.11-slim
WORKDIR /app
COPY apps/audio_portal/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY apps/audio_portal ./apps/audio_portal
COPY .streamlit/config.toml ./.streamlit/config.toml
RUN useradd -m portal
USER portal
EXPOSE 8501
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"
CMD ["streamlit", "run", "apps/audio_portal/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
