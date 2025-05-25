import asyncio
import httpx
from typing import Optional

from datatypes import VideoRequest, MediaMetadata
from config_manager import load_config_and_omdb_key

OMDB_API_URL = "http://www.omdbapi.com/"

async def get_media_metadata(
    api_key: str, 
    request: VideoRequest,
    client: httpx.AsyncClient
) -> Optional[MediaMetadata]:
    """ 
    Fetches movie metadata from the OMDb API based on the VideoRequest.
    Prioritizes IMDb ID if available, otherwise uses title and year.
    """
    params = {"apikey": api_key, "type": "movie"}

    if request.imdb_id:
        params["i"] = request.imdb_id
    elif request.title:
        params["t"] = request.title
        if request.year:
            params["y"] = str(request.year)
    else:
        print("Error: VideoRequest must have either title or imdb_id.")
        return None

    print(f"[OMDb Client] Sending request with params: {params}")

    try:
        response = await client.get(OMDB_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        print(f"[OMDb Client] Response: {data}")

        if data.get("Response") == "True":
            # Parse year (handle ranges like "2010-2015")
            year_str = data.get("Year", "")
            year_int: Optional[int] = None
            if year_str:
                if "–" in year_str:  # en-dash
                    year_int = int(year_str.split("–")[0])
                elif "-" in year_str:  # hyphen
                    year_int = int(year_str.split("-")[0])
                else:
                    try:
                        year_int = int(year_str)
                    except ValueError:
                        print(f"Warning: Could not parse year from OMDb: {year_str}")

            return MediaMetadata(
                confirmed_title=data.get("Title", request.title or "Unknown Title"),
                year=year_int,
                imdb_id=data.get("imdbID", request.imdb_id or ""),
                plot=data.get("Plot"),
                poster_url=data.get("Poster") if data.get("Poster") != "N/A" else None,
                director=data.get("Director"),
                actors=data.get("Actors"),
                runtime=data.get("Runtime"),
                genre=data.get("Genre"),
                rating=data.get("imdbRating") if data.get("imdbRating") != "N/A" else None
            )
        else:
            print(f"OMDb API Error: {data.get('Error', 'Unknown error')}")
            return None
    except httpx.HTTPStatusError as e:
        print(f"HTTP error occurred: {e.response.text if e.response else e}")
        return None
    except httpx.RequestError as e:
        print(f"Request error occurred: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None


async def main():
    """Example usage of the omdb_client."""
    try:
        app_config, omdb_api_key = load_config_and_omdb_key()
    except Exception as e:
        print(f"Failed to load configuration: {e}")
        return

    if not omdb_api_key:
        print("OMDb API key not found in .env. Please add OMDB_API_KEY to your .env file.")
        return

    # Example movie requests
    test_movies = [
        # VideoRequest(title="The Matrix", destination_tv="any", year=1999),
        # VideoRequest(imdb_id="tt0133093", destination_tv="any"),  # The Matrix by IMDb ID
        # VideoRequest(title="Inception", destination_tv="any", year=2010),
        # VideoRequest(title="The Shawshank Redemption", destination_tv="any"),
        VideoRequest(title="Split", destination_tv="any"),
    ]

    async with httpx.AsyncClient() as client:
        for i, req in enumerate(test_movies):
            print(f"\n--- Test {i + 1} ---")
            print(f"Request: {req}")
            metadata = await get_media_metadata(omdb_api_key, req, client)
            if metadata:
                print("Successfully fetched metadata:")
                print(f"  Title: {metadata.confirmed_title}")
                print(f"  Year: {metadata.year}")
                print(f"  IMDb ID: {metadata.imdb_id}")
                print(f"  Director: {metadata.director}")
                print(f"  Actors: {metadata.actors}")
                print(f"  Genre: {metadata.genre}")
                print(f"  Runtime: {metadata.runtime}")
                print(f"  Rating: {metadata.rating}")
                print(f"  Plot: {metadata.plot[:80] if metadata.plot else 'N/A'}...")
            else:
                print("Failed to fetch metadata.")

if __name__ == "__main__":
    asyncio.run(main()) 