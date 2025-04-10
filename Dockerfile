FROM python:3.12

# Update the package repository and upgrade installed packages
RUN apt-get update && apt-get upgrade -y

WORKDIR /documentation_qa
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Upgrade pip
RUN pip install --upgrade pip

# Copy the entire project into the image
COPY . .

# Create necessary directories if they don't exist
RUN mkdir -p /documentation_qa/docs_content /documentation_qa/logs

# Install Python packages from requirements.txt
RUN pip install -r requirements.txt --use-deprecated=legacy-resolver

# Flask and API dependencies
RUN python -m pip install "connexion[flask]"
RUN python -m pip install "connexion[uvicorn]"

# Install additional dependencies that might be needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set proper permissions
RUN chmod -R 755 /documentation_qa

# Expose ports for both Flask and Streamlit
EXPOSE 5000 8501

# Create an entrypoint script to run both services
RUN echo '#!/bin/bash\n\
echo "Starting Documentation Assistant..."\n\
# Start the Flask API server\n\
uvicorn main:app --host 0.0.0.0 --port 5000 &\n\
# Wait for the server to start\n\
sleep 5\n\
streamlit run streamlit_app.py\n\
' > /documentation_qa/entrypoint.sh && chmod +x /documentation_qa/entrypoint.sh

# Set the entrypoint
ENTRYPOINT ["/documentation_qa/entrypoint.sh"]

# Alternative command to run just the API
# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]