from pydantic import BaseModel
from typing import Literal

class VideoRequest(BaseModel):
    title: str # Name of the movie, TV Show, or general video content to be found.
    season: int | None = None # Season number of the TV Show to be found. (If requesting a TV show, this is required.)
    episode: int | None = None # Episode number of the TV Show to be found. (If requesting a TV show, this is required.)
    content_type: Literal["movie", "tv", "general"] # Type of content to be found.
    destination_tv: str # Name of the Roku device to send the video to (from config). Or IP address of the Roku device.


class VideoResolved(BaseModel):
    title: str # Name fo the found video content.
    season: int | None = None # Season number of the TV Show to be found. (If requesting a TV show, this is required.)
    episode: int | None = None # Episode number of the TV Show to be found. (If requesting a TV show, this is required.)
    content_type: Literal["movie", "tv", "general"] # Type of content found.
    destination_tv: str # Name of the Roku device to send the video to (from config). Or IP address of the Roku device.
    url: str # URL of the video to be sent to the Roku device.
    media_type: str # Type of media to be sent to the Roku device. Ex. mp4, m3u8, etc.


class RokuDevice(BaseModel):
    name: str  # User-friendly name for the Roku device
    ip_address: str  # IP address of the Roku device


class AppConfig(BaseModel):
    roku_devices: list[RokuDevice]

    
