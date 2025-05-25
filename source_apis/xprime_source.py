import sys

sys.path.append("..")  # Add parent directory to path for imports

from abc import ABC
from video_source_api import VideoSourceAPI
from datatypes import (
    MediaMetadata,
    VideoStream,
    VideoSources,
    AppConfig,
    VideoRequest,
    SearchResult,
)
import httpx
import asyncio
from typing import Dict, Any


class XPrimeStreamAPI(VideoSourceAPI, ABC):
    """Base video source API that searches for movie streams on xprime.tv endpoints."""

    def __init__(self, config: AppConfig, client: httpx.AsyncClient, base_url: str):
        """
        Initialize the XPrime API with a configurable base URL.

        Args:
            config: The application configuration
            client: The httpx client for making requests
            base_url: The base URL for the XPrime API endpoint
        """
        super().__init__(config, client)
        self.base_url = base_url

    @property
    def name(self) -> str:
        # Extract the domain from the base_url to make the name more descriptive
        domain = (
            self.base_url.replace("https://", "").replace("http://", "").split("/")[0]
        )
        return f"XPrime ({domain}) Movie Streamer"

    async def search_streams(
        self, metadata: MediaMetadata, original_request: VideoRequest
    ) -> VideoSources:
        """
        Searches for movie streams on xprime.tv based on the movie title.

        Args:
            metadata: A MediaMetadata object containing movie information from TMDB.
            original_request: The original VideoRequest that initiated the search.

        Returns:
            A VideoSources object containing found streams and detailed search results.
        """
        streams = []
        search_results = []

        # Use the confirmed title from TMDB for the search
        movie_name = metadata.confirmed_title
        params = {"name": movie_name}

        # Add year to the search if available
        if metadata.year:
            params["fallback_year"] = metadata.year

        year_info = f" ({metadata.year})" if metadata.year else ""
        print(f"[{self.name}] Searching for streams for: '{movie_name}{year_info}'")

        try:
            response = await self.client.get(self.base_url, params=params, timeout=15.0)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "ok" and "streams" in data and data["streams"]:
                available_streams = data["streams"]
                print(f"[{self.name}] Found {len(available_streams)} quality option(s)")

                # Order of preferred qualities
                preferred_qualities = ["1080P", "720P", "480P", "360P"]

                # Try to add streams in preferred quality order
                for quality in preferred_qualities:
                    if quality in available_streams:
                        stream_url = available_streams[quality]

                        # Try to determine media type from URL
                        media_type = self._get_media_type_from_url(stream_url)

                        streams.append(
                            VideoStream(
                                url=stream_url,
                                media_type=media_type,
                                quality=quality,
                                from_request=original_request,
                                source_api=self.name,
                            )
                        )
                        print(
                            f"[{self.name}] Added {quality} stream: {stream_url[:60]}..."
                        )

                # Add any remaining qualities not in our preferred list
                for quality, url in available_streams.items():
                    if quality not in preferred_qualities:
                        media_type = self._get_media_type_from_url(url)
                        streams.append(
                            VideoStream(
                                url=url,
                                media_type=media_type,
                                quality=quality,
                                from_request=original_request,
                                source_api=self.name,
                            )
                        )
                        print(f"[{self.name}] Added {quality} stream: {url[:60]}...")

                # Create successful search result
                search_results.append(
                    self.create_search_result(
                        success=True,
                        streams_found=len(streams),
                        message=f"Successfully found {len(streams)} stream(s) in qualities: {', '.join(available_streams.keys())}",
                        status=data.get("status", "ok"),
                    )
                )
            else:
                # No streams found - capture detailed information
                print(f"[{self.name}] No streams found for '{movie_name}'")

                api_status = data.get("status", "unknown")
                api_message = data.get("message", "No streams available")

                if api_status != "ok":
                    print(f"[{self.name}] API status: {api_status}")
                if data.get("message"):
                    print(f"[{self.name}] API message: {data.get('message')}")

                # Create detailed search result for no streams found
                detailed_message = f"No streams found for '{movie_name}'"
                if api_message and api_message != "No streams available":
                    detailed_message += f". API message: {api_message}"

                search_results.append(
                    self.create_search_result(
                        success=False,
                        streams_found=0,
                        message=detailed_message,
                        status=api_status,
                        error_details=f"API returned: {data}" if data else None,
                    )
                )

        except httpx.HTTPStatusError as e:
            error_message = f"HTTP {e.response.status_code} error"
            error_details = (
                f"Response: {e.response.text[:200]}"
                if e.response.text
                else "No response body"
            )

            if e.response.status_code == 429:
                error_message = "Rate limited (HTTP 429). Try again in a few seconds"
                error_details += ". Note: xprime.tv has rate limiting. Consider waiting between requests."
                print(
                    f"[{self.name}] Rate limited (HTTP 429). Try again in a few seconds."
                )
                print(
                    f"[{self.name}] Note: xprime.tv has rate limiting. Consider waiting between requests."
                )
            else:
                print(f"[{self.name}] HTTP error occurred: {e.response.status_code}")

            if e.response.text:
                print(f"[{self.name}] Response: {e.response.text[:200]}")

            search_results.append(
                self.create_search_result(
                    success=False,
                    streams_found=0,
                    message=error_message,
                    status=f"HTTP_{e.response.status_code}",
                    error_details=error_details,
                )
            )

        except httpx.RequestError as e:
            error_message = f"Request error: {str(e)}"
            print(f"[{self.name}] Request error occurred: {e}")

            search_results.append(
                self.create_search_result(
                    success=False,
                    streams_found=0,
                    message=error_message,
                    status="REQUEST_ERROR",
                    error_details=str(e),
                )
            )

        except Exception as e:
            error_message = f"Unexpected error: {str(e)}"
            print(f"[{self.name}] Unexpected error: {e}")

            search_results.append(
                self.create_search_result(
                    success=False,
                    streams_found=0,
                    message=error_message,
                    status="UNKNOWN_ERROR",
                    error_details=str(e),
                )
            )

        return VideoSources(sources=streams, search_results=search_results)

    def _get_media_type_from_url(self, url: str) -> str:
        """
        Attempts to derive the media type from the URL.

        Args:
            url: The stream URL

        Returns:
            The media type (e.g., 'mp4', 'mkv'), defaults to 'mp4'
        """
        try:
            # Remove query parameters
            path_part = url.split("?")[0].lower()

            # Check for common video extensions
            video_extensions = [
                "mp4",
                "mkv",
                "avi",
                "mov",
                "wmv",
                "flv",
                "webm",
                "m3u8",
            ]

            for ext in video_extensions:
                if path_part.endswith(f".{ext}"):
                    return ext

            # Check if extension is in the path
            if "." in path_part:
                potential_ext = path_part.split(".")[-1]
                if len(potential_ext) <= 4 and potential_ext.isalnum():
                    return potential_ext
        except:
            pass

        # Default to mp4 if unable to determine
        return "mp4"


# Multiple XPrime API variants for different endpoints
class XPrimeMainAPI(XPrimeStreamAPI):
    """XPrime API using the main xprime.tv endpoint."""

    def __init__(self, config: AppConfig, client: httpx.AsyncClient):
        super().__init__(config, client, "https://xprime.tv/primebox")


class XPrimeBackendAPI(XPrimeStreamAPI):
    """XPrime API using the backend.xprime.tv endpoint."""

    def __init__(self, config: AppConfig, client: httpx.AsyncClient):
        super().__init__(config, client, "https://backend.xprime.tv/primebox")


class XPrimePrimenetAPI(VideoSourceAPI, ABC):
    """XPrime API using the backend.xprime.tv/primenet endpoint with TMDB ID."""

    def __init__(self, config: AppConfig, client: httpx.AsyncClient):
        """
        Initialize the XPrime Primenet API.

        Args:
            config: The application configuration
            client: The httpx client for making requests
        """
        super().__init__(config, client)
        self.base_url = "https://backend.xprime.tv/primenet"

    @property
    def name(self) -> str:
        return "XPrime Primenet Movie Streamer"

    async def search_streams(
        self, metadata: MediaMetadata, original_request: VideoRequest
    ) -> VideoSources:
        """
        Searches for movie streams on xprime.tv primenet endpoint using TMDB ID.

        Args:
            metadata: A MediaMetadata object containing movie information from TMDB.
            original_request: The original VideoRequest that initiated the search.

        Returns:
            A VideoSources object containing found streams and detailed search results.
        """
        streams = []
        search_results = []

        # Check if we have a TMDB ID
        if not metadata.tmdb_id:
            error_message = "No TMDB ID available for primenet search"
            print(f"[{self.name}] {error_message}")
            search_results.append(
                self.create_search_result(
                    success=False,
                    streams_found=0,
                    message=error_message,
                    status="NO_TMDB_ID",
                )
            )
            return VideoSources(sources=streams, search_results=search_results)

        movie_name = metadata.confirmed_title
        year_info = f" ({metadata.year})" if metadata.year else ""
        print(
            f"[{self.name}] Searching for streams for: '{movie_name}{year_info}' (TMDB ID: {metadata.tmdb_id})"
        )

        params = {"id": metadata.tmdb_id}

        try:
            response = await self.client.get(self.base_url, params=params, timeout=15.0)
            response.raise_for_status()
            data = response.json()

            # Check if we got a URL in the response
            if "url" in data and data["url"]:
                stream_url = data["url"]
                print(f"[{self.name}] Found stream URL: {stream_url[:60]}...")

                # Try to determine media type from URL
                media_type = self._get_media_type_from_url(stream_url)

                # Since this endpoint doesn't specify quality, we'll assume it's the best available
                quality = "HD"  # Default quality since primenet doesn't specify

                streams.append(
                    VideoStream(
                        url=stream_url,
                        media_type=media_type,
                        quality=quality,
                        from_request=original_request,
                        source_api=self.name,
                    )
                )

                # Create successful search result
                search_results.append(
                    self.create_search_result(
                        success=True,
                        streams_found=1,
                        message=f"Successfully found stream for TMDB ID {metadata.tmdb_id}",
                        status="ok",
                    )
                )
            else:
                # No URL found in response
                print(
                    f"[{self.name}] No stream URL found in response for TMDB ID {metadata.tmdb_id}"
                )

                # Create detailed search result for no streams found
                error_message = f"No stream URL found for TMDB ID {metadata.tmdb_id}"
                if data:
                    error_message += f". Response: {data}"

                search_results.append(
                    self.create_search_result(
                        success=False,
                        streams_found=0,
                        message=error_message,
                        status="NO_URL_FOUND",
                        error_details=f"API returned: {data}" if data else None,
                    )
                )

        except httpx.HTTPStatusError as e:
            error_message = f"HTTP {e.response.status_code} error"
            error_details = (
                f"Response: {e.response.text[:200]}"
                if e.response.text
                else "No response body"
            )

            if e.response.status_code == 404:
                error_message = (
                    f"Movie not found for TMDB ID {metadata.tmdb_id} (HTTP 404)"
                )
                print(f"[{self.name}] Movie not found for TMDB ID {metadata.tmdb_id}")
            elif e.response.status_code == 429:
                error_message = "Rate limited (HTTP 429). Try again in a few seconds"
                error_details += ". Note: xprime.tv has rate limiting. Consider waiting between requests."
                print(
                    f"[{self.name}] Rate limited (HTTP 429). Try again in a few seconds."
                )
            else:
                print(f"[{self.name}] HTTP error occurred: {e.response.status_code}")

            if e.response.text:
                print(f"[{self.name}] Response: {e.response.text[:200]}")

            search_results.append(
                self.create_search_result(
                    success=False,
                    streams_found=0,
                    message=error_message,
                    status=f"HTTP_{e.response.status_code}",
                    error_details=error_details,
                )
            )

        except httpx.RequestError as e:
            error_message = f"Request error: {str(e)}"
            print(f"[{self.name}] Request error occurred: {e}")

            search_results.append(
                self.create_search_result(
                    success=False,
                    streams_found=0,
                    message=error_message,
                    status="REQUEST_ERROR",
                    error_details=str(e),
                )
            )

        except Exception as e:
            error_message = f"Unexpected error: {str(e)}"
            print(f"[{self.name}] Unexpected error: {e}")

            search_results.append(
                self.create_search_result(
                    success=False,
                    streams_found=0,
                    message=error_message,
                    status="UNKNOWN_ERROR",
                    error_details=str(e),
                )
            )

        return VideoSources(sources=streams, search_results=search_results)

    def _get_media_type_from_url(self, url: str) -> str:
        """
        Attempts to derive the media type from the URL.

        Args:
            url: The stream URL

        Returns:
            The media type (e.g., 'mp4', 'mkv'), defaults to 'mp4'
        """
        try:
            # Remove query parameters
            path_part = url.split("?")[0].lower()

            # Check for common video extensions
            video_extensions = [
                "mp4",
                "mkv",
                "avi",
                "mov",
                "wmv",
                "flv",
                "webm",
                "m3u8",
            ]

            for ext in video_extensions:
                if path_part.endswith(f".{ext}"):
                    return ext

            # Check if extension is in the path
            if "." in path_part:
                potential_ext = path_part.split(".")[-1]
                if len(potential_ext) <= 4 and potential_ext.isalnum():
                    return potential_ext
        except:
            pass

        # Default to mp4 if unable to determine
        return "mp4"


# Example usage for testing
if __name__ == "__main__":
    import asyncio
    from config_manager import load_config_and_tmdb_keys
    from tmdb_client import get_media_metadata

    async def test_all_xprime_apis():
        print("--- Testing All XPrime Stream APIs ---")

        try:
            config, tmdb_api_key, tmdb_read_access_token = load_config_and_tmdb_keys()
        except Exception as e:
            print(f"Error loading config: {e}")
            return

        # Test with a popular movie
        test_title = "The Matrix"
        test_year = 1999
        test_description = "A popular movie to test all endpoints"

        print(f"\n{'='*60}")
        print(f"Testing: {test_title} ({test_year}) - {test_description}")
        print(f"{'='*60}")

        # Use API key if available, otherwise try read access token
        api_key = tmdb_api_key or tmdb_read_access_token
        if api_key:
            # Get real metadata from TMDB
            async with httpx.AsyncClient() as client:
                test_request = VideoRequest(
                    title=test_title, year=test_year, destination_tv="any"
                )
                test_metadata = await get_media_metadata(api_key, test_request, client)

                if not test_metadata:
                    print(f"Failed to get metadata from TMDB for {test_title}")
                    return
        else:
            print("TMDB API key or read access token not found. Exiting test.")
            return

        # Test all XPrime API variants
        api_classes = [XPrimeMainAPI, XPrimeBackendAPI, XPrimePrimenetAPI]

        async with httpx.AsyncClient() as client:
            for api_class in api_classes:
                print(f"\n{'-'*50}")
                api_instance = api_class(config=config, client=client)
                print(f"Testing: {api_instance.name}")
                print(f"Base URL: {api_instance.base_url}")

                try:
                    sources = await api_instance.search_streams(
                        test_metadata, test_request
                    )

                    print(f"Results Summary:")
                    print(f"- Streams found: {len(sources.sources)}")
                    print(f"- Search results: {len(sources.search_results)}")

                    if sources.sources:
                        print(f"\nFound {len(sources.sources)} stream(s):")
                        for i, stream in enumerate(sources.sources, 1):
                            print(
                                f"{i}. Quality: {stream.quality}, Type: {stream.media_type}"
                            )
                            print(f"   URL: {stream.url[:80]}...")
                    else:
                        print("No streams found")

                    # Display detailed search results
                    print(f"\nDetailed Search Results:")
                    for result in sources.search_results:
                        status_icon = "✓" if result.success else "✗"
                        print(f"{status_icon} {result.api_name}")
                        print(f"  Message: {result.message}")
                        if result.status:
                            print(f"  Status: {result.status}")
                        if result.error_details and not result.success:
                            details = result.error_details
                            if len(details) > 200:
                                details = details[:200] + "..."
                            print(f"  Details: {details}")

                except Exception as e:
                    print(f"Error testing {api_instance.name}: {e}")

                # Add a small delay between API calls to avoid rate limiting
                await asyncio.sleep(1)

    asyncio.run(test_all_xprime_apis())
