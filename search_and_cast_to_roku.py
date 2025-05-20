import requests
import json

# --- Roku Configuration ---
# Replace with your Roku's IP address
ROKU_IP = "10.0.0.16" # bedroom: 10.0.0.205
# Media Assistant's channel ID from the Roku store, or your preferred channel ID
ROKU_CHANNEL_ID = "782875"


def get_video_stream_url(movie_name, preferred_quality="1080P"):
    """
    Fetches video stream information from xprime.tv for a given movie name.

    Args:
        movie_name (str): The name of the movie or show.
        preferred_quality (str): The preferred video quality (e.g., "1080P", "720P").

    Returns:
        str | None: The URL of the video stream if found, otherwise None.
    """
    base_url = "https://xprime.tv/primebox"
    params = {"name": movie_name}
    print(f"Searching for video stream for: {movie_name} (Preferred quality: {preferred_quality})")
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        data = response.json()

        if data.get("status") == "ok" and "streams" in data and data["streams"]:
            streams = data["streams"]
            if preferred_quality in streams:
                print(f"Found {preferred_quality} stream.")
                return streams[preferred_quality]
            else:
                # Fallback to the first available stream if preferred quality is not found
                fallback_quality = next(iter(streams))
                print(f"{preferred_quality} not found. Falling back to first available: {fallback_quality}")
                return streams[fallback_quality]
        else:
            print(f"Could not find any streams for '{movie_name}' or status not 'ok'.")
            print(f"Response from xprime.tv: {data}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"An error occurred while fetching video stream data: {e}")
        return None
    except json.JSONDecodeError:
        print(f"Failed to decode JSON response from xprime.tv. Response text: {response.text[:500]}")
        return None


def cast_to_roku(media_url, video_name, video_format="mp4"):
    """
    Casts the given media URL to a Roku TV.

    Args:
        media_url (str): The URL of the media to cast.
        video_name (str): The name/title of the video.
        video_format (str): The format of the video (e.g., "mp4", "mkv").

    Returns:
        bool: True if the cast command was sent successfully, False otherwise.
    """
    if not media_url:
        print("No media URL provided. Cannot cast to Roku.")
        return False

    # Attempt to derive video format from URL if not mp4 and seems like a valid extension
    # This is a simple heuristic.
    if video_format == "mp4": # Default behavior from original script was mp4
        try:
            path_part = media_url.split('?')[0]
            if '.' in path_part:
                potential_format = path_part.split('.')[-1].lower()
                if len(potential_format) <= 4 and potential_format.isalnum(): # e.g. mkv, avi
                    video_format = potential_format
                    print(f"Derived video format from URL: {video_format}")
        except Exception:
            pass # Stick to default if parsing fails


    params = {
        "u": media_url,
        "t": "v",  # t=v for video, t=a for audio
        "videoName": video_name,
        "videoFormat": video_format
    }
    roku_launch_url = f"http://{ROKU_IP}:8060/launch/{ROKU_CHANNEL_ID}"

    print(f"Attempting to cast to Roku: '{video_name}' (Format: {video_format})")
    print(f"Media URL: {media_url}")
    print(f"Roku POST URL: {roku_launch_url}")
    print(f"POST Params: {params}")

    try:
        post_response = requests.post(roku_launch_url, params=params, timeout=10) # Increased timeout
        post_response.raise_for_status()
        print(f"Successfully sent cast command to Roku (Status: {post_response.status_code}).")
        return True
    except requests.exceptions.Timeout:
        print(f"Error casting to Roku: The request timed out. Check if Roku ({ROKU_IP}) is online and responsive.")
        return False
    except requests.exceptions.ConnectionError:
        print(f"Error casting to Roku: Connection refused. Check if Roku ({ROKU_IP}) is online and the IP is correct.")
        return False
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while casting to Roku: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Roku response status: {e.response.status_code}")
            print(f"Roku response text: {e.response.text[:500]}")
        return False


if __name__ == "__main__":
    # --- Configuration for the search ---
    # You can change the movie title here or adapt the script to take it as a command-line argument
    movie_title_to_search = input("Enter the movie title to search for: ")
    # Preferred video quality for streaming.
    # The script will try this first, then fall back to any other available stream.
    preferred_stream_quality = "1080P"
    # --- End Configuration ---

    print(f"--- Starting search and cast for: {movie_title_to_search} ---")

    stream_url = get_video_stream_url(movie_title_to_search, preferred_quality=preferred_stream_quality)

    if stream_url:
        print(f"Successfully retrieved stream URL: {stream_url}")
        # The video name for Roku will be the movie title searched.
        # The video format will be attempted to be derived from the URL, defaulting to 'mp4'.
        cast_successful = cast_to_roku(
            media_url=stream_url,
            video_name=movie_title_to_search.title()
            # video_format will be determined by cast_to_roku
        )

        if cast_successful:
            print(f"--- Successfully initiated casting for: {movie_title_to_search} ---")
        else:
            print(f"--- Failed to cast: {movie_title_to_search} ---")
    else:
        print(f"Could not get a stream URL for '{movie_title_to_search}'. Cannot proceed with casting.")
        print(f"--- Failed to find stream for: {movie_title_to_search} ---") 