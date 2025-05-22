import asyncio
import argparse
import httpx
import pkgutil
import importlib
from pathlib import Path
from typing import List, Optional

from datatypes import VideoRequest, MediaMetadata, VideoStream, RokuDevice, AppConfig, VideoSources
from config_manager import load_config_and_omdb_key
from omdb_client import get_media_metadata
from video_source_api import VideoSourceAPI
from roku_caster import cast_to_roku

# --- Helper Functions ---
async def select_roku_device(config: AppConfig) -> Optional[RokuDevice]:
    """Allows the user to select a Roku device from the configured list."""
    if not config.roku_devices:
        print("No Roku devices configured in config.yaml.")
        return None
    
    print("\nAvailable Roku Devices:")
    for i, device in enumerate(config.roku_devices):
        print(f"  {i+1}. {device.name} ({device.ip_address})")
    
    while True:
        try:
            choice = input(f"Select a Roku device (1-{len(config.roku_devices)}): ")
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(config.roku_devices):
                return config.roku_devices[choice_idx]
            else:
                print("Invalid selection. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number.")

async def select_video_stream(streams: List[VideoStream]) -> Optional[VideoStream]:
    """Allows the user to select a video stream from a list."""
    if not streams:
        print("No video streams found to select from.")
        return None

    print("\nAvailable Video Streams:")
    for i, stream in enumerate(streams):
        title = stream.from_request.title or "(Title not specified in original request)"
        print(f"  {i+1}. {title} - Quality: {stream.quality}, Type: {stream.media_type}, Source: {stream.url[:50]}...")

    while True:
        try:
            choice = input(f"Select a video stream (1-{len(streams)}): ")
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(streams):
                return streams[choice_idx]
            else:
                print("Invalid selection. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number.")

def load_video_source_apis(config: AppConfig, client: httpx.AsyncClient) -> List[VideoSourceAPI]:
    """Dynamically loads all VideoSourceAPI implementations from the source_apis directory."""
    source_apis_path = Path(__file__).parent / "source_apis"
    loaded_apis: List[VideoSourceAPI] = []

    print(f"\nLoading video source APIs from: {source_apis_path}")

    for finder, name, ispkg in pkgutil.iter_modules([str(source_apis_path)]):
        if not ispkg:  # Ensure it's a module, not a package
            try:
                module_name = f"source_apis.{name}"
                module = importlib.import_module(module_name)
                for attribute_name in dir(module):
                    attribute = getattr(module, attribute_name)
                    if isinstance(attribute, type) and issubclass(attribute, VideoSourceAPI) and attribute is not VideoSourceAPI:
                        try:
                            instance = attribute(config=config, client=client)
                            print(f"  Successfully loaded and initialized: {instance.name}")
                            loaded_apis.append(instance)
                        except Exception as e:
                            print(f"  Error initializing API {attribute_name} from {module_name}: {e}")
            except Exception as e:
                print(f"  Error loading module {name} from source_apis: {e}")
    
    if not loaded_apis:
        print("No video source APIs were successfully loaded.")
    return loaded_apis

# --- Main Application Logic ---
async def main_workflow():
    parser = argparse.ArgumentParser(description="Search for movies and cast them to a Roku device.")
    parser.add_argument("-t", "--title", type=str, help="Title of the movie.")
    parser.add_argument("-i", "--imdb_id", type=str, help="IMDb ID of the movie.")
    parser.add_argument("-y", "--year", type=int, help="Year of release.")
    parser.add_argument("--tv", type=str, help="Name or IP of the destination Roku TV (must match a configured device). If not provided, will prompt.")

    args = parser.parse_args()

    if not args.title and not args.imdb_id:
        parser.error("At least one of --title (-t) or --imdb_id (-i) must be provided.")

    # 1. Load Configuration
    print("Loading configuration...")
    try:
        app_config, omdb_api_key = load_config_and_omdb_key()
    except Exception as e:
        print(f"Fatal Error: Could not load configuration. {e}")
        return

    if not omdb_api_key:
        print("Fatal Error: OMDB_API_KEY not found in .env file or .env is missing. Please set it up.")
        return

    # Determine target Roku device
    target_device: Optional[RokuDevice] = None
    if args.tv:
        for dev in app_config.roku_devices:
            if dev.name == args.tv or dev.ip_address == args.tv:
                target_device = dev
                break
        if not target_device:
            print(f"Warning: Roku device '{args.tv}' not found in configuration. Will prompt for selection.")
    
    if not target_device:
        target_device = await select_roku_device(app_config)
        if not target_device:
            print("No Roku device selected. Exiting.")
            return
    print(f"Selected Roku device: {target_device.name}")

    # 2. Create VideoRequest
    try:
        video_req = VideoRequest(
            title=args.title,
            imdb_id=args.imdb_id,
            year=args.year,
            destination_tv=target_device.name
        )
    except ValueError as ve:
        print(f"Error in video request parameters: {ve}")
        return

    print(f"\nVideo Request: Title='{video_req.title}', IMDb='{video_req.imdb_id}', Year='{video_req.year}'")

    async with httpx.AsyncClient(timeout=20.0) as client:
        # 3. Get MediaMetadata from OMDb
        print("\nFetching metadata from OMDb...")
        media_info = await get_media_metadata(omdb_api_key, video_req, client)

        if not media_info:
            print("Could not retrieve movie information from OMDb. Exiting.")
            return
        
        print(f"Successfully fetched OMDb Metadata for: '{media_info.confirmed_title}' ({media_info.imdb_id})")
        print(f"  Year: {media_info.year}")
        print(f"  Director: {media_info.director}")
        print(f"  Genre: {media_info.genre}")
        if media_info.plot:
            print(f"  Plot: {media_info.plot[:100]}...")

        # 4. Load and Use VideoSourceAPIs
        video_source_apis = load_video_source_apis(app_config, client)
        all_found_streams: List[VideoStream] = []

        if not video_source_apis:
            print("No video source APIs available to search for streams. Exiting.")
            return

        for api_instance in video_source_apis:
            print(f"\nSearching for streams using: {api_instance.name}...")
            try:
                sources: VideoSources = await api_instance.search_streams(media_info, video_req)
                if sources.sources:
                    print(f"  Found {len(sources.sources)} stream(s) from {api_instance.name}.")
                    all_found_streams.extend(sources.sources)
                else:
                    print(f"  No streams found by {api_instance.name}.")
            except Exception as e:
                print(f"  Error during stream search with {api_instance.name}: {e}")
        
        if not all_found_streams:
            print("\nNo video streams found from any source. Exiting.")
            return

        # Validate that we have real streams (not dummy/example URLs)
        real_streams = []
        for stream in all_found_streams:
            if not stream.url.startswith(("https://example-", "http://example-")):
                real_streams.append(stream)
            else:
                print(f"Skipping dummy/example stream: {stream.url[:50]}...")

        if not real_streams:
            print("\nNo real video streams found (only dummy/example URLs). Cannot cast to Roku.")
            print("This usually means the video source APIs failed or are rate limited.")
            return

        # 5. User Selects Stream
        selected_stream = await select_video_stream(real_streams)
        if not selected_stream:
            print("No video stream selected. Exiting.")
            return
        
        print(f"\nSelected stream: {selected_stream.url[:70]}... ({selected_stream.quality})")

        # 6. Cast to Roku
        print(f"\nPreparing to cast to {target_device.name}...")
        cast_successful = await cast_to_roku(selected_stream, target_device, app_config, client)

        if cast_successful:
            print(f"\nSuccessfully initiated casting of '{media_info.confirmed_title}' to {target_device.name}.")
        else:
            print(f"\nFailed to cast '{media_info.confirmed_title}' to {target_device.name}.")

if __name__ == "__main__":
    print("--- Autocast Movie Caster Starting --- ")
    asyncio.run(main_workflow())
    print("\n--- Autocast Movie Caster Finished ---") 