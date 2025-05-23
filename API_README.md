# Autocast Movie Caster API

A FastAPI-based web service for searching movies and casting them to Roku devices.

## Features

- 🎬 Search for movies using OMDb API
- 📺 Cast movies to configured Roku devices
- 🔍 Multiple video source integrations
- 🐳 Docker containerization
- 📚 Automatic API documentation
- 🏥 Health monitoring

## Quick Start

### Using Docker Compose (Recommended)

1. Clone the repository and navigate to the project directory
2. Create a `.env` file with your OMDb API key:
   ```
   OMDB_API_KEY=your_omdb_api_key_here
   ```
3. Update `config.yaml` with your Roku device information
4. Run the application:
   ```bash
   docker-compose up -d
   ```

The API will be available at `http://localhost:8000`

### Using Docker

```bash
# Build the image
docker build -t autocast-api .

# Run the container
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/.env:/app/.env:ro \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  --name autocast \
  autocast-api
```

### Local Development

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Create `.env` file with your OMDb API key

3. Run the FastAPI server:
   ```bash
   uvicorn app:app --reload --host 0.0.0.0 --port 8000
   ```

## API Endpoints

### Health Check

- **GET** `/health` - Check API health and configuration status

### Device Management

- **GET** `/devices` - List all configured Roku devices

### Movie Operations

- **POST** `/search` - Search for a movie and get available streams
- **POST** `/cast` - Cast a movie to a Roku device
- **POST** `/cast-background` - Cast a movie in the background

### API Documentation

- **GET** `/docs` - Interactive Swagger UI documentation
- **GET** `/redoc` - ReDoc API documentation

## Request Examples

### Search for a Movie

```bash
curl -X POST "http://localhost:8000/search" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "The Matrix",
    "year": 1999
  }'
```

### Cast a Movie

```bash
curl -X POST "http://localhost:8000/cast" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "The Matrix",
    "year": 1999,
    "destination_tv": "Office TV",
    "stream_index": 0
  }'
```

### List Roku Devices

```bash
curl -X GET "http://localhost:8000/devices"
```

## Configuration

### Environment Variables

- `OMDB_API_KEY` - Your OMDb API key (required)

### config.yaml

```yaml
roku_devices:
  - name: 'Office TV'
    ip_address: '10.0.0.16'
  - name: 'Bedroom TV'
    ip_address: '10.0.0.205'
```

## Development

### Adding Video Source APIs

1. Create a new file in the `source_apis/` directory
2. Implement the `VideoSourceAPI` abstract class
3. The API will automatically load your new source

### Running Tests

```bash
python -m pytest tests/
```

## Production Deployment

For production, use the nginx configuration:

```bash
docker-compose --profile production up -d
```

This will run the API behind an nginx reverse proxy on port 80.

## Troubleshooting

### Common Issues

1. **OMDB API Key Missing**: Ensure your `.env` file contains `OMDB_API_KEY=your_key`
2. **Roku Device Not Found**: Check that your Roku devices are correctly configured in `config.yaml`
3. **No Streams Found**: This usually indicates the video source APIs are rate-limited or unavailable

### Logs

```bash
# View logs
docker-compose logs -f autocast-api

# View specific container logs
docker logs autocast
```

## API Response Examples

### Search Response

```json
{
	"metadata": {
		"confirmed_title": "The Matrix",
		"year": 1999,
		"imdb_id": "tt0133093",
		"plot": "A computer hacker learns...",
		"director": "Lana Wachowski, Lilly Wachowski",
		"genre": "Action, Sci-Fi"
	},
	"streams": [
		{
			"url": "https://example.com/stream.mp4",
			"media_type": "mp4",
			"quality": "1080P",
			"source_api": "XPrime.tv Movie Streamer"
		}
	]
}
```

### Cast Response

```json
{
	"success": true,
	"message": "Successfully initiated casting to Office TV",
	"metadata": {
		"confirmed_title": "The Matrix",
		"year": 1999,
		"imdb_id": "tt0133093"
	},
	"stream_info": {
		"url": "https://example.com/stream.mp4",
		"media_type": "mp4",
		"quality": "1080P",
		"source_api": "multiple"
	}
}
```
