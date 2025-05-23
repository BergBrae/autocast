from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import httpx
import asyncio
import pkgutil
import importlib
from pathlib import Path

from datatypes import (
    VideoRequest,
    MediaMetadata,
    VideoStream,
    RokuDevice,
    AppConfig,
    VideoSources,
)
from config_manager import load_config_and_omdb_key
from omdb_client import get_media_metadata
from video_source_api import VideoSourceAPI
from roku_caster import cast_to_roku

# FastAPI app instance
app = FastAPI(
    title="Autocast Movie Caster API",
    description="API for searching movies and casting them to Roku devices",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables for config and HTTP client
app_config: Optional[AppConfig] = None
omdb_api_key: Optional[str] = None
http_client: Optional[httpx.AsyncClient] = None
video_source_apis: List[VideoSourceAPI] = []


# Pydantic models for API requests/responses
class SearchRequest(BaseModel):
    title: Optional[str] = Field(None, description="Title of the movie")
    imdb_id: Optional[str] = Field(None, description="IMDb ID of the movie")
    year: Optional[int] = Field(None, description="Year of release")


class CastRequest(BaseModel):
    title: Optional[str] = Field(None, description="Title of the movie")
    imdb_id: Optional[str] = Field(None, description="IMDb ID of the movie")
    year: Optional[int] = Field(None, description="Year of release")
    destination_tv: str = Field(
        ..., description="Name or IP of the destination Roku TV"
    )
    stream_index: Optional[int] = Field(
        0, description="Index of the stream to cast (default: 0)"
    )


class StreamInfo(BaseModel):
    url: str
    media_type: str
    quality: str
    source_api: str


class SearchResponse(BaseModel):
    metadata: MediaMetadata
    streams: List[StreamInfo]


class CastResponse(BaseModel):
    success: bool
    message: str
    metadata: Optional[MediaMetadata] = None
    stream_info: Optional[StreamInfo] = None


class DeviceInfo(BaseModel):
    name: str
    ip_address: str


def load_video_source_apis(
    config: AppConfig, client: httpx.AsyncClient
) -> List[VideoSourceAPI]:
    """Dynamically loads all VideoSourceAPI implementations from the source_apis directory."""
    source_apis_path = Path(__file__).parent / "source_apis"
    loaded_apis: List[VideoSourceAPI] = []

    for finder, name, ispkg in pkgutil.iter_modules([str(source_apis_path)]):
        if not ispkg:  # Ensure it's a module, not a package
            try:
                module_name = f"source_apis.{name}"
                module = importlib.import_module(module_name)
                for attribute_name in dir(module):
                    attribute = getattr(module, attribute_name)
                    if (
                        isinstance(attribute, type)
                        and issubclass(attribute, VideoSourceAPI)
                        and attribute is not VideoSourceAPI
                    ):
                        try:
                            instance = attribute(config=config, client=client)
                            loaded_apis.append(instance)
                        except Exception as e:
                            print(
                                f"Error initializing API {attribute_name} from {module_name}: {e}"
                            )
            except Exception as e:
                print(f"Error loading module {name} from source_apis: {e}")

    return loaded_apis


@app.on_event("startup")
async def startup_event():
    """Initialize configuration and HTTP client on startup."""
    global app_config, omdb_api_key, http_client, video_source_apis

    try:
        app_config, omdb_api_key = load_config_and_omdb_key()
        if not omdb_api_key:
            print("Warning: OMDB_API_KEY not found in .env file")

        http_client = httpx.AsyncClient(timeout=20.0)
        video_source_apis = load_video_source_apis(app_config, http_client)

        print(f"Loaded {len(video_source_apis)} video source APIs")
        print(f"Configured {len(app_config.roku_devices)} Roku devices")

    except Exception as e:
        print(f"Error during startup: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    global http_client
    if http_client:
        await http_client.aclose()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "omdb_api_configured": omdb_api_key is not None,
        "roku_devices_count": len(app_config.roku_devices) if app_config else 0,
        "video_source_apis_count": len(video_source_apis),
    }


@app.get("/devices", response_model=List[DeviceInfo])
async def get_devices():
    """Get list of configured Roku devices."""
    if not app_config:
        raise HTTPException(status_code=500, detail="Configuration not loaded")

    return [
        DeviceInfo(name=device.name, ip_address=device.ip_address)
        for device in app_config.roku_devices
    ]


@app.post("/search", response_model=SearchResponse)
async def search_movie(request: SearchRequest):
    """Search for a movie and return metadata and available streams."""
    if not omdb_api_key:
        raise HTTPException(status_code=500, detail="OMDB API key not configured")

    if not request.title and not request.imdb_id:
        raise HTTPException(
            status_code=400, detail="Either title or imdb_id must be provided"
        )

    # Create VideoRequest (using a dummy destination_tv since it's required)
    video_req = VideoRequest(
        title=request.title,
        imdb_id=request.imdb_id,
        year=request.year,
        destination_tv="api_search",  # Dummy value for search
    )

    # Get metadata from OMDb
    metadata = await get_media_metadata(omdb_api_key, video_req, http_client)
    if not metadata:
        raise HTTPException(status_code=404, detail="Movie not found in OMDb database")

    # Search for streams using all available APIs
    all_streams = []
    for api_instance in video_source_apis:
        try:
            sources: VideoSources = await api_instance.search_streams(
                metadata, video_req
            )
            for stream in sources.sources:
                all_streams.append(
                    StreamInfo(
                        url=stream.url,
                        media_type=stream.media_type,
                        quality=stream.quality,
                        source_api=api_instance.name,
                    )
                )
        except Exception as e:
            print(f"Error searching with {api_instance.name}: {e}")

    return SearchResponse(metadata=metadata, streams=all_streams)


@app.post("/cast", response_model=CastResponse)
async def cast_movie(request: CastRequest):
    """Cast a movie to a Roku device."""
    if not omdb_api_key:
        raise HTTPException(status_code=500, detail="OMDB API key not configured")

    if not request.title and not request.imdb_id:
        raise HTTPException(
            status_code=400, detail="Either title or imdb_id must be provided"
        )

    # Find the target Roku device
    target_device = None
    for device in app_config.roku_devices:
        if (
            device.name == request.destination_tv
            or device.ip_address == request.destination_tv
        ):
            target_device = device
            break

    if not target_device:
        raise HTTPException(
            status_code=404,
            detail=f"Roku device '{request.destination_tv}' not found in configuration",
        )

    # Create VideoRequest
    video_req = VideoRequest(
        title=request.title,
        imdb_id=request.imdb_id,
        year=request.year,
        destination_tv=target_device.name,
    )

    # Get metadata from OMDb
    metadata = await get_media_metadata(omdb_api_key, video_req, http_client)
    if not metadata:
        raise HTTPException(status_code=404, detail="Movie not found in OMDb database")

    # Search for streams using all available APIs
    all_streams = []
    for api_instance in video_source_apis:
        try:
            sources: VideoSources = await api_instance.search_streams(
                metadata, video_req
            )
            for stream in sources.sources:
                all_streams.append(stream)
        except Exception as e:
            print(f"Error searching with {api_instance.name}: {e}")

    if not all_streams:
        return CastResponse(
            success=False,
            message="No video streams found for this movie",
            metadata=metadata,
        )

    # Select the stream (use stream_index, default to 0)
    stream_index = min(request.stream_index, len(all_streams) - 1)
    selected_stream = all_streams[stream_index]

    # Cast to Roku
    success = await cast_to_roku(
        selected_stream, target_device, app_config, http_client
    )

    stream_info = StreamInfo(
        url=selected_stream.url,
        media_type=selected_stream.media_type,
        quality=selected_stream.quality,
        source_api="multiple",  # Could be improved to track which API provided the stream
    )

    if success:
        return CastResponse(
            success=True,
            message=f"Successfully initiated casting to {target_device.name}",
            metadata=metadata,
            stream_info=stream_info,
        )
    else:
        return CastResponse(
            success=False,
            message=f"Failed to cast to {target_device.name}",
            metadata=metadata,
            stream_info=stream_info,
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
