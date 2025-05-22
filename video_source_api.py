from abc import ABC, abstractmethod
import httpx

from datatypes import MediaMetadata, VideoSources, AppConfig, VideoRequest

class VideoSourceAPI(ABC):
    """Abstract base class for video source APIs."""

    def __init__(self, config: AppConfig, client: httpx.AsyncClient):
        """
        Initializes the API client.

        Args:
            config: The application configuration, which may contain API keys or other settings.
            client: An httpx.AsyncClient instance for making HTTP requests.
        """
        self.config = config
        self.client = client

    @abstractmethod
    async def search_streams(self, metadata: MediaMetadata, original_request: VideoRequest) -> VideoSources:
        """
        Searches for video streams based on the provided media metadata.

        Args:
            metadata: A MediaMetadata object containing information about the desired video (e.g., from OMDb).
            original_request: The original VideoRequest that initiated the search.
        
        Returns:
            A VideoSources object containing a list of found VideoStream objects.
            Returns VideoSources with an empty list if no streams are found.
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Returns the user-friendly name of this video source API."""
        pass

# Example of how a concrete implementation might look (in a separate file):
#
# from .video_source_api import VideoSourceAPI
# from datatypes import MediaMetadata, VideoStream, VideoSources, AppConfig
# import httpx
#
# class ExampleImdbStreamAPI(VideoSourceAPI):
#     @property
#     def name(self) -> str:
#         return "Example IMDb ID Based Streamer"
#
#     async def search_streams(self, metadata: MediaMetadata) -> VideoSources:
#         streams = []
#         if metadata.imdb_id:
#             # Hypothetical API that takes an IMDb ID
#             # In a real scenario, you would make an HTTP request here using self.client
#             # and parse the response to create VideoStream objects.
#             dummy_url = f"https://example-streamer.com/stream/{metadata.confirmed_title}"
#             print(f"{self.name}: Found potential stream for {metadata.confirmed_title} at {dummy_url}")
#             streams.append(
#                 VideoStream(
#                     url=dummy_url,
#                     media_type="mp4", 
#                     quality="1080p",
#                     # The from_request would ideally be the original VideoRequest,
#                     # which isn't directly passed here. This might need refinement
#                     # if strict back-linking to the original request is needed per stream.
#                     # For now, we'll create a placeholder or adapt later.
#                     from_request=None # Placeholder, needs to be addressed if this field is critical here
#                 )
#             )
#         else:
#             print(f"{self.name}: Cannot search without IMDb ID.")
#         return VideoSources(sources=streams) 