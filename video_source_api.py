from abc import ABC, abstractmethod
import httpx

from datatypes import MediaMetadata, VideoSources, AppConfig, VideoRequest, SearchResult


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
    async def search_streams(
        self, metadata: MediaMetadata, original_request: VideoRequest
    ) -> VideoSources:
        """
        Searches for video streams based on the provided media metadata.

        Args:
            metadata: A MediaMetadata object containing information about the desired video (e.g., from OMDb).
            original_request: The original VideoRequest that initiated the search.

        Returns:
            A VideoSources object containing a list of found VideoStream objects and search results.
            The VideoSources should include a SearchResult object with details about the search operation,
            especially when no streams are found.
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Returns the user-friendly name of this video source API."""
        pass

    def create_search_result(
        self,
        success: bool,
        streams_found: int,
        message: str = None,
        status: str = None,
        error_details: str = None,
    ) -> SearchResult:
        """
        Helper method to create a SearchResult object.

        Args:
            success: Whether the search was successful
            streams_found: Number of streams found
            message: Optional message from the API
            status: Optional API status
            error_details: Optional additional error details

        Returns:
            A SearchResult object
        """
        return SearchResult(
            api_name=self.name,
            success=success,
            streams_found=streams_found,
            message=message,
            status=status,
            error_details=error_details,
        )


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
#         search_results = []
#
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
#                     from_request=original_request
#                 )
#             )
#             search_results.append(self.create_search_result(True, 1, "Successfully found stream"))
#         else:
#             print(f"{self.name}: Cannot search without IMDb ID.")
#             search_results.append(self.create_search_result(False, 0, "Cannot search without IMDb ID"))
#
#         return VideoSources(sources=streams, search_results=search_results)
