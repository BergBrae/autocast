import sys

sys.path.append("..")  # Add parent directory to path for imports

from video_source_api import VideoSourceAPI
from datatypes import MediaMetadata, VideoStream, VideoSources, AppConfig, VideoRequest
import httpx
import asyncio
from typing import Dict, Any


class XPrimeStreamAPI(VideoSourceAPI):
    """Video source API that searches for movie streams on xprime.tv."""

    @property
    def name(self) -> str:
        return "XPrime.tv Movie Streamer"

    async def search_streams(
        self, metadata: MediaMetadata, original_request: VideoRequest
    ) -> VideoSources:
        """
        Searches for movie streams on xprime.tv based on the movie title.

        Args:
            metadata: A MediaMetadata object containing movie information from OMDb.
            original_request: The original VideoRequest that initiated the search.

        Returns:
            A VideoSources object containing found streams.
        """
        streams = []

        # Use the confirmed title from OMDb for the search
        movie_name = metadata.confirmed_title
        base_url = "https://xprime.tv/primebox"
        params = {"name": movie_name}

        # Add year to the search if available
        if metadata.year:
            params["fallback_year"] = metadata.year

        year_info = f" ({metadata.year})" if metadata.year else ""
        print(f"[{self.name}] Searching for streams for: '{movie_name}{year_info}'")

        try:
            response = await self.client.get(base_url, params=params, timeout=15.0)
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
                            )
                        )
                        print(f"[{self.name}] Added {quality} stream: {url[:60]}...")
            else:
                print(f"[{self.name}] No streams found for '{movie_name}'")
                if data.get("status") != "ok":
                    print(f"[{self.name}] API status: {data.get('status', 'unknown')}")
                if data.get("message"):
                    print(f"[{self.name}] API message: {data.get('message')}")

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
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
        except httpx.RequestError as e:
            print(f"[{self.name}] Request error occurred: {e}")
        except Exception as e:
            print(f"[{self.name}] Unexpected error: {e}")

        return VideoSources(sources=streams)

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
    from config_manager import load_config_and_omdb_key
    from omdb_client import get_media_metadata

    async def test_xprime():
        print("--- Testing XPrime Stream API ---")

        try:
            config, omdb_api_key = load_config_and_omdb_key()
        except Exception as e:
            print(f"Error loading config: {e}")
            return

        if not omdb_api_key:
            print("OMDb API key not found. Using dummy metadata.")
            # Create test metadata
            test_metadata = MediaMetadata(
                confirmed_title="The Matrix",
                imdb_id="tt0133093",
                year=1999,
                director="Lana Wachowski, Lilly Wachowski",
                genre="Action, Sci-Fi",
            )
            test_request = VideoRequest(title="The Matrix", destination_tv="any")
        else:
            # Get real metadata from OMDb
            async with httpx.AsyncClient() as client:
                test_request = VideoRequest(title="The Matrix", destination_tv="any")
                test_metadata = await get_media_metadata(
                    omdb_api_key, test_request, client
                )

                if not test_metadata:
                    print("Failed to get metadata from OMDb")
                    return

        # Test the XPrime API
        async with httpx.AsyncClient() as client:
            xprime_api = XPrimeStreamAPI(config=config, client=client)
            print(f"\nSearching with {xprime_api.name}...")

            sources = await xprime_api.search_streams(test_metadata, test_request)

            if sources.sources:
                print(f"\nFound {len(sources.sources)} stream(s):")
                for i, stream in enumerate(sources.sources, 1):
                    print(f"{i}. Quality: {stream.quality}, Type: {stream.media_type}")
                    print(f"   URL: {stream.url[:80]}...")
            else:
                print("No streams found")

    asyncio.run(test_xprime())
