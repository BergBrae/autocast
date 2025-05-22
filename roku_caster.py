import httpx
import asyncio
from typing import Optional

from datatypes import VideoStream, RokuDevice, AppConfig

# Media Assistant's channel ID from the Roku store
MEDIA_ASSISTANT_CHANNEL_ID = "782875"

async def cast_to_roku(
    stream: VideoStream, 
    device: RokuDevice, 
    app_config: AppConfig,
    client: httpx.AsyncClient
) -> bool:
    """
    Casts a video stream to a Roku device using Media Assistant.

    Uses Roku's External Control Protocol (ECP) to launch Media Assistant
    and pass the stream URL.

    Args:
        stream: The VideoStream object to cast.
        device: The RokuDevice object to cast to.
        app_config: The application configuration.
        client: An httpx.AsyncClient for making requests.

    Returns:
        True if casting was successful, False otherwise.
    """
    print(f"\nAttempting to cast to Roku device: {device.name} at {device.ip_address}")
    print(f"  Media Title: {stream.from_request.title if stream.from_request else 'Unknown Title'}")
    print(f"  Stream URL: {stream.url}")
    print(f"  Media Type: {stream.media_type}")
    print(f"  Quality: {stream.quality}")

    # Roku ECP endpoint for launching Media Assistant
    launch_url = f"http://{device.ip_address}:8060/launch/{MEDIA_ASSISTANT_CHANNEL_ID}"
    
    # Parameters for Media Assistant
    # u = URL, t = type (v for video), videoName = title, videoFormat = format
    params = {
        "u": stream.url,
        "t": "v",  # v for video, a for audio
        "videoName": stream.from_request.title if stream.from_request and stream.from_request.title else "Movie",
        "videoFormat": stream.media_type
    }

    print(f"  Sending POST to: {launch_url}")
    print(f"  With parameters: {params}")

    try:
        response = await client.post(launch_url, params=params, timeout=10.0)
        response.raise_for_status()
        print(f"  Roku ECP Response Status: {response.status_code}")
        
        if response.status_code == 200:
            print(f"Successfully launched Media Assistant on {device.name}.")
            return True
        else:
            print(f"Unexpected response status from Roku: {response.status_code}")
            return False
        
    except httpx.HTTPStatusError as e:
        print(f"  Error: HTTP {e.response.status_code} from Roku device {device.name}")
        if e.response.text:
            print(f"  Response: {e.response.text[:200]}")
        return False
    except httpx.TimeoutException:
        print(f"  Error: Request timed out. Check if Roku ({device.ip_address}) is online and responsive.")
        return False
    except httpx.ConnectError:
        print(f"  Error: Connection refused. Check if Roku ({device.ip_address}) is online and the IP is correct.")
        return False
    except httpx.RequestError as e:
        print(f"  Error connecting to Roku device {device.name}: {e}")
        return False
    except Exception as e:
        print(f"  Unexpected error during casting to {device.name}: {e}")
        return False


# Example usage (for testing this module directly)
async def main():
    from config_manager import load_config_and_omdb_key
    from datatypes import VideoRequest

    print("--- Roku Caster Test --- ")
    try:
        app_config, _ = load_config_and_omdb_key()
        if not app_config.roku_devices:
            print("No Roku devices configured in config.yaml. Add at least one to test.")
            dummy_device = RokuDevice(name="Test Roku", ip_address="192.168.1.100")
            app_config.roku_devices.append(dummy_device)
            print("Using a dummy Roku device for this test.")
    except Exception as e:
        print(f"Error loading config: {e}. Using a dummy device.")
        dummy_device = RokuDevice(name="Test Roku", ip_address="192.168.1.100")
        app_config = AppConfig(roku_devices=[dummy_device])

    chosen_device = app_config.roku_devices[0]

    # Create a test VideoRequest and VideoStream
    test_video_request = VideoRequest(
        title="Big Buck Bunny", 
        destination_tv=chosen_device.name
    )
    test_stream = VideoStream(
        url="http://distribution.bbb3d.renderfarming.net/video/mp4/bbb_sunflower_1080p_30fps_normal.mp4",
        media_type="mp4",
        quality="1080p",
        from_request=test_video_request
    )

    async with httpx.AsyncClient() as client:
        success = await cast_to_roku(test_stream, chosen_device, app_config, client)
        if success:
            print("\nCasting successful!")
        else:
            print("\nCasting failed.")

if __name__ == "__main__":
    asyncio.run(main()) 