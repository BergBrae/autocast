import asyncio
import httpx
from typing import Optional, List, Dict, Any

from datatypes import VideoRequest, MediaMetadata
from config_manager import load_config_and_tmdb_keys

TMDB_API_BASE_URL = "https://api.themoviedb.org/3"


async def search_movie_by_title(
    api_key: str,
    title: str,
    year: Optional[int] = None,
    client: httpx.AsyncClient = None,
) -> Optional[Dict[str, Any]]:
    """
    Search for a movie by title using TMDB API.
    Returns the first matching result or None if no matches found.
    """
    params = {"api_key": api_key, "query": title, "include_adult": "false"}

    if year:
        params["year"] = str(year)

    url = f"{TMDB_API_BASE_URL}/search/movie"

    try:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        if data.get("results") and len(data["results"]) > 0:
            # Return the first result (most relevant)
            return data["results"][0]
        else:
            print(f"[TMDB Client] No movies found for title: {title}")
            return None

    except httpx.HTTPStatusError as e:
        print(
            f"[TMDB Client] HTTP error during search: {e.response.text if e.response else e}"
        )
        return None
    except Exception as e:
        print(f"[TMDB Client] Error during search: {e}")
        return None


async def get_movie_details(
    api_key: str, tmdb_id: int, client: httpx.AsyncClient
) -> Optional[Dict[str, Any]]:
    """
    Get detailed movie information by TMDB ID.
    """
    url = f"{TMDB_API_BASE_URL}/movie/{tmdb_id}"
    params = {"api_key": api_key, "append_to_response": "credits,external_ids"}

    try:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        print(
            f"[TMDB Client] HTTP error getting movie details: {e.response.text if e.response else e}"
        )
        return None
    except Exception as e:
        print(f"[TMDB Client] Error getting movie details: {e}")
        return None


async def find_movie_by_imdb_id(
    api_key: str, imdb_id: str, client: httpx.AsyncClient
) -> Optional[Dict[str, Any]]:
    """
    Find a movie by IMDb ID using TMDB's find endpoint.
    """
    url = f"{TMDB_API_BASE_URL}/find/{imdb_id}"
    params = {"api_key": api_key, "external_source": "imdb_id"}

    try:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        if data.get("movie_results") and len(data["movie_results"]) > 0:
            return data["movie_results"][0]
        else:
            print(f"[TMDB Client] No movie found for IMDb ID: {imdb_id}")
            return None

    except httpx.HTTPStatusError as e:
        print(
            f"[TMDB Client] HTTP error finding movie by IMDb ID: {e.response.text if e.response else e}"
        )
        return None
    except Exception as e:
        print(f"[TMDB Client] Error finding movie by IMDb ID: {e}")
        return None


def format_runtime(runtime_minutes: Optional[int]) -> Optional[str]:
    """Convert runtime from minutes to a formatted string."""
    if not runtime_minutes:
        return None

    hours = runtime_minutes // 60
    minutes = runtime_minutes % 60

    if hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"


def extract_director(credits: Dict[str, Any]) -> Optional[str]:
    """Extract director name from credits."""
    crew = credits.get("crew", [])
    directors = [person["name"] for person in crew if person.get("job") == "Director"]
    return ", ".join(directors) if directors else None


def extract_main_actors(credits: Dict[str, Any], limit: int = 5) -> Optional[str]:
    """Extract main actors from credits."""
    cast = credits.get("cast", [])
    main_actors = [person["name"] for person in cast[:limit]]
    return ", ".join(main_actors) if main_actors else None


async def get_media_metadata(
    api_key: str, request: VideoRequest, client: httpx.AsyncClient
) -> Optional[MediaMetadata]:
    """
    Fetches movie metadata from the TMDB API based on the VideoRequest.
    Prioritizes IMDb ID if available, otherwise uses title and year.
    """
    movie_data = None

    # First try to find by IMDb ID if provided
    if request.imdb_id:
        print(f"[TMDB Client] Searching by IMDb ID: {request.imdb_id}")
        movie_data = await find_movie_by_imdb_id(api_key, request.imdb_id, client)

    # If not found by IMDb ID or no IMDb ID provided, search by title
    if not movie_data and request.title:
        print(f"[TMDB Client] Searching by title: {request.title}")
        movie_data = await search_movie_by_title(
            api_key, request.title, request.year, client
        )

    if not movie_data:
        print("[TMDB Client] No movie found matching the request")
        return None

    # Get detailed information
    tmdb_id = movie_data.get("id")
    if not tmdb_id:
        print("[TMDB Client] No TMDB ID found in movie data")
        return None

    print(f"[TMDB Client] Getting detailed information for TMDB ID: {tmdb_id}")
    detailed_data = await get_movie_details(api_key, tmdb_id, client)

    if not detailed_data:
        print("[TMDB Client] Failed to get detailed movie information")
        return None

    # Extract metadata
    title = detailed_data.get("title", request.title or "Unknown Title")

    # Parse release date for year
    release_date = detailed_data.get("release_date", "")
    year = None
    if release_date:
        try:
            year = int(release_date.split("-")[0])
        except (ValueError, IndexError):
            print(
                f"[TMDB Client] Could not parse year from release date: {release_date}"
            )

    # Get IMDb ID from external IDs
    external_ids = detailed_data.get("external_ids", {})
    imdb_id = external_ids.get("imdb_id") or request.imdb_id

    # Build poster URL
    poster_path = detailed_data.get("poster_path")
    poster_url = None
    if poster_path:
        poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}"

    # Extract credits information
    credits = detailed_data.get("credits", {})
    director = extract_director(credits)
    actors = extract_main_actors(credits)

    # Format genres
    genres = detailed_data.get("genres", [])
    genre_str = ", ".join([g["name"] for g in genres]) if genres else None

    # Format runtime
    runtime = format_runtime(detailed_data.get("runtime"))

    # Get rating (TMDB uses vote_average, convert to string for compatibility)
    rating = detailed_data.get("vote_average")
    rating_str = str(rating) if rating else None

    print(f"[TMDB Client] Successfully processed metadata for: {title}")

    return MediaMetadata(
        confirmed_title=title,
        year=year,
        tmdb_id=tmdb_id,
        imdb_id=imdb_id,
        plot=detailed_data.get("overview"),
        poster_url=poster_url,
        director=director,
        actors=actors,
        runtime=runtime,
        genre=genre_str,
        rating=rating_str,
    )


async def main():
    """Example usage of the TMDB client."""
    try:
        app_config, tmdb_api_key, tmdb_read_access_token = load_config_and_tmdb_keys()
    except Exception as e:
        print(f"Failed to load configuration: {e}")
        return

    # Use API key if available, otherwise try read access token
    api_key = tmdb_api_key or tmdb_read_access_token
    if not api_key:
        print(
            "TMDB API key or read access token not found in .env. Please add TMDB_API_KEY or TMDB_READ_ACCESS_TOKEN to your .env file."
        )
        return

    # Example movie requests
    test_movies = [
        VideoRequest(title="The Matrix", destination_tv="any", year=1999),
        VideoRequest(
            imdb_id="tt0133093", destination_tv="any"
        ),  # The Matrix by IMDb ID
        VideoRequest(title="Inception", destination_tv="any", year=2010),
        VideoRequest(title="The Shawshank Redemption", destination_tv="any"),
        VideoRequest(title="The Wolf of Wall Street", destination_tv="any"),
    ]

    async with httpx.AsyncClient() as client:
        for i, req in enumerate(test_movies):
            print(f"\n--- Test {i + 1} ---")
            print(f"Request: {req}")
            metadata = await get_media_metadata(api_key, req, client)
            if metadata:
                print("Successfully fetched metadata:")
                print(f"  Title: {metadata.confirmed_title}")
                print(f"  Year: {metadata.year}")
                print(f"  TMDB ID: {metadata.tmdb_id}")
                print(f"  IMDb ID: {metadata.imdb_id}")
                print(f"  Director: {metadata.director}")
                print(f"  Actors: {metadata.actors}")
                print(f"  Genre: {metadata.genre}")
                print(f"  Runtime: {metadata.runtime}")
                print(f"  Rating: {metadata.rating}")
                print(f"  Plot: {metadata.plot[:80] if metadata.plot else 'N/A'}...")
                print(f"  Poster URL: {metadata.poster_url}")
            else:
                print("Failed to fetch metadata.")


if __name__ == "__main__":
    asyncio.run(main())
