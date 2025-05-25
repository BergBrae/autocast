import httpx
import asyncio
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from datatypes import MediaMetadata

from datatypes import VideoStream, RokuDevice, AppConfig

# Media Assistant's channel ID from the Roku store
MEDIA_ASSISTANT_CHANNEL_ID = "782875"


async def check_roku_responsive(device: RokuDevice, client: httpx.AsyncClient) -> bool:
    """
    Check if the Roku device is responsive (powered on and ready).

    Args:
        device: The RokuDevice to check.
        client: An httpx.AsyncClient for making requests.

    Returns:
        True if the device is responsive, False otherwise.
    """
    try:
        response = await client.get(
            f"http://{device.ip_address}:8060/query/device-info", timeout=3.0
        )
        return response.status_code == 200
    except (httpx.TimeoutException, httpx.ConnectError, httpx.RequestError):
        return False


async def power_on_roku(device: RokuDevice, client: httpx.AsyncClient) -> bool:
    """
    Send a power-on command to the Roku device.

    Args:
        device: The RokuDevice to power on.
        client: An httpx.AsyncClient for making requests.

    Returns:
        True if the power-on command was sent successfully, False otherwise.
    """
    try:
        power_url = f"http://{device.ip_address}:8060/keypress/PowerOn"
        response = await client.post(power_url, timeout=5.0)
        return response.status_code in [200, 202]
    except (httpx.TimeoutException, httpx.ConnectError, httpx.RequestError):
        return False


async def wait_for_roku_ready(
    device: RokuDevice, client: httpx.AsyncClient, max_wait_time: int = 30
) -> bool:
    """
    Wait for the Roku device to become responsive after powering on.

    Args:
        device: The RokuDevice to wait for.
        client: An httpx.AsyncClient for making requests.
        max_wait_time: Maximum time to wait in seconds.

    Returns:
        True if the device becomes responsive, False if timeout.
    """
    print(f"  Waiting for {device.name} to boot up...")

    for attempt in range(max_wait_time):
        await asyncio.sleep(1)
        if await check_roku_responsive(device, client):
            print(f"  {device.name} is now responsive (took {attempt + 1} seconds)")
            return True

        # Show progress every 5 seconds
        if (attempt + 1) % 5 == 0:
            print(f"  Still waiting... ({attempt + 1}/{max_wait_time} seconds)")

    print(
        f"  Timeout: {device.name} did not become responsive within {max_wait_time} seconds"
    )
    return False


async def cast_to_roku(
    stream: VideoStream,
    device: RokuDevice,
    app_config: AppConfig,
    client: httpx.AsyncClient,
    media_metadata: Optional["MediaMetadata"] = None,
) -> bool:
    """
    Casts a video stream to a Roku device using Media Assistant.

    Uses Roku's External Control Protocol (ECP) to launch Media Assistant
    and pass the stream URL. Handles the case where the TV is powered off
    by first powering it on and waiting for it to boot up.

    Args:
        stream: The VideoStream object to cast.
        device: The RokuDevice object to cast to.
        app_config: The application configuration.
        client: An httpx.AsyncClient for making requests.
        media_metadata: Optional MediaMetadata from TMDB API. If provided,
                       the confirmed_title will be used instead of the user input.

    Returns:
        True if casting was successful, False otherwise.
    """
    # Determine the title to use - prefer TMDB confirmed title over user input
    display_title = "Unknown Title"
    if media_metadata and media_metadata.confirmed_title:
        display_title = media_metadata.confirmed_title
    elif stream.from_request and stream.from_request.title:
        display_title = stream.from_request.title

    print(f"\nAttempting to cast to Roku device: {device.name} at {device.ip_address}")
    print(f"  Media Title: {display_title}")
    print(f"  Stream URL: {stream.url}")
    print(f"  Media Type: {stream.media_type}")
    print(f"  Quality: {stream.quality}")

    # Check if the Roku is responsive (powered on)
    print(f"  Checking if {device.name} is responsive...")
    is_responsive = await check_roku_responsive(device, client)

    if not is_responsive:
        print(f"  {device.name} appears to be powered off or in deep sleep")
        print(f"  Attempting to power on {device.name}...")

        power_on_success = await power_on_roku(device, client)
        if not power_on_success:
            print(f"  Failed to send power-on command to {device.name}")
            return False

        print(f"  Power-on command sent successfully")

        # Wait for the TV to boot up and become responsive
        ready = await wait_for_roku_ready(device, client, max_wait_time=30)
        if not ready:
            print(f"  {device.name} did not become responsive after power-on")
            print(f"  This could be due to:")
            print(f"    - TV taking longer than expected to boot")
            print(f"    - Network connectivity issues")
            print(f"    - TV not supporting remote power-on")
            return False
    else:
        print(f"  {device.name} is already powered on and responsive")

    # Roku ECP endpoint for launching Media Assistant
    launch_url = f"http://{device.ip_address}:8060/launch/{MEDIA_ASSISTANT_CHANNEL_ID}"

    # Parameters for Media Assistant
    # u = URL, t = type (v for video), videoName = title, videoFormat = format
    params = {
        "u": stream.url,
        "t": "v",  # v for video, a for audio
        "videoName": display_title,
        "videoFormat": stream.media_type,
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
        print(
            f"  Error: Request timed out. Check if Roku ({device.ip_address}) is online and responsive."
        )
        return False
    except httpx.ConnectError:
        print(
            f"  Error: Connection refused. Check if Roku ({device.ip_address}) is online and the IP is correct."
        )
        return False
    except httpx.RequestError as e:
        print(f"  Error connecting to Roku device {device.name}: {e}")
        return False
    except Exception as e:
        print(f"  Unexpected error during casting to {device.name}: {e}")
        return False


# Example usage (for testing this module directly)
async def main():
    from config_manager import load_config_and_tmdb_keys
    from datatypes import VideoRequest

    print("--- Roku Caster Test --- ")
    try:
        app_config, _, _ = load_config_and_tmdb_keys()
        if not app_config.roku_devices:
            print(
                "No Roku devices configured in config.yaml. Add at least one to test."
            )
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
        title="Big Buck Bunny", destination_tv=chosen_device.name
    )
    test_stream = VideoStream(
        url="http://distribution.bbb3d.renderfarming.net/video/mp4/bbb_sunflower_1080p_30fps_normal.mp4",
        media_type="mp4",
        quality="1080p",
        from_request=test_video_request,
        source_api="Test API",
    )

    async with httpx.AsyncClient() as client:
        success = await cast_to_roku(test_stream, chosen_device, app_config, client)
        if success:
            print("\nCasting successful!")
        else:
            print("\nCasting failed.")


if __name__ == "__main__":
    asyncio.run(main())
