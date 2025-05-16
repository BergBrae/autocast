import requests, urllib.parse

roku_ip   = "10.0.0.16"
media_url = "https://macdn.hakunaymatata.com/resource/9f8240cfcf2d9fb53c16f1abfc3ed05a.mp4?Expires=1748612044&Signature=G3RSeWryx3Tf0xc9AntuyKE33hyqOGCgvueW77phBttzP~Oki0ppSOfB3s1zgLYSoxkpiVUFYUbxURRU3XHaA55wPUpFg5ptn3hYySPCVY5ujRi4GoZC8jUzqrU01Z5HRXBYEOOMA8k5ebDulouvXvUcUgjIk5PXUnG3I6dwMGQQxPsklTATfVVJseUSpwbJFgaEPO~EDjmYtWe~vSyROu8fx7rpjEX5h9SrwZn6UQLSm7yzGgSvzc-kjIe9xu7270BLYh4nYWvffXdGnMbFPS2bd5yx9~qtQPscTVibbKmwZ41JPaB8KZ7wYvFKp2Bu59gNJJdBekas5ocVhXeyIQ__&Key-Pair-Id=KMHN1LQ1HEUPL"

params = {
    "u": media_url,          # media URL
    "t": "v",                # a=audio, v=video
    "videoName": "Title",
    "videoFormat": "mp4"
}

# 782875 is Media Assistant’s channel ID from the Roku store
requests.post(f"http://{roku_ip}:8060/launch/782875", params=params, timeout=3).raise_for_status()
