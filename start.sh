#!/bin/bash

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    echo "OMDB_API_KEY=your_omdb_api_key_here" > .env
    echo "Please edit .env file and add your OMDb API key"
    echo "You can get one from: http://www.omdbapi.com/apikey.aspx"
    exit 1
fi

# Check if Docker is available
if command -v docker-compose &> /dev/null; then
    echo "Starting with Docker Compose..."
    docker-compose up -d
    echo "API is starting at http://localhost:8000"
    echo "View logs with: docker-compose logs -f"
elif command -v docker &> /dev/null; then
    echo "Starting with Docker..."
    docker build -t autocast-api .
    docker run -d \
        -p 8000:8000 \
        -v $(pwd)/.env:/app/.env:ro \
        -v $(pwd)/config.yaml:/app/config.yaml:ro \
        --name autocast \
        autocast-api
    echo "API is starting at http://localhost:8000"
    echo "View logs with: docker logs -f autocast"
else
    echo "Docker not found. Starting locally..."
    if [ ! -d .venv ]; then
        echo "Creating virtual environment..."
        python3 -m venv .venv
    fi
    
    echo "Activating virtual environment..."
    source .venv/bin/activate
    
    echo "Installing dependencies..."
    pip install -r requirements.txt
    
    echo "Starting FastAPI server..."
    uvicorn app:app --reload --host 0.0.0.0 --port 8000
fi 