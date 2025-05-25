from pydantic import BaseModel, root_validator
from typing import Optional, List, Dict, Any


class VideoRequest(BaseModel):
    title: Optional[str] = None  # Name of the movie to be found.
    imdb_id: Optional[str] = None  # IMDB ID of the movie to be found.
    year: Optional[int] = None  # Year of the movie to be found.
    destination_tv: str  # Name of the Roku device to send the video to (from config). Or IP address of the Roku device.

    @root_validator(pre=True)
    @classmethod
    def check_title_or_imdb_id_present(cls, values):
        if not values.get("title") and not values.get("imdb_id"):
            raise ValueError('Either "title" or "imdb_id" must be provided')
        return values


class MediaMetadata(BaseModel):
    confirmed_title: str
    year: Optional[int] = None
    tmdb_id: Optional[int] = None  # TMDB ID (primary identifier)
    imdb_id: Optional[str] = None  # IMDb ID (secondary, may not always be available)
    plot: Optional[str] = None
    poster_url: Optional[str] = None
    director: Optional[str] = None
    actors: Optional[str] = None
    runtime: Optional[str] = None
    genre: Optional[str] = None
    rating: Optional[str] = None  # IMDb rating


class VideoStream(BaseModel):
    url: str  # URL of the video to be sent to the Roku device.
    media_type: str  # Type of media to be sent to the Roku device. Ex. mp4, m3u8, etc.
    quality: str  # Quality of the video to be sent to the Roku device. Ex. 1080p, 720p, 480p, etc.
    from_request: VideoRequest  # Request that was used to find the video stream.


class SearchResult(BaseModel):
    """Represents the result of a search operation from a video source API."""

    api_name: str  # Name of the API that performed the search
    success: bool  # Whether the search was successful
    streams_found: int  # Number of streams found
    message: Optional[str] = None  # Message from the API (error message, status, etc.)
    status: Optional[str] = None  # API status if available
    error_details: Optional[str] = None  # Additional error details if any


class VideoSources(BaseModel):
    sources: List[VideoStream]  # List of video streams to be sent to the Roku device.
    search_results: List[SearchResult] = []  # Results from each API search attempt


class RokuDevice(BaseModel):
    name: str  # User-friendly name for the Roku device
    ip_address: str  # IP address of the Roku device


class AppConfig(BaseModel):
    roku_devices: list[RokuDevice]
    # omdb_api_key: Optional[str] = None # Removed, will be loaded from .env
