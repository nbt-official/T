import os
import requests
import re
import json
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def process_links():
    final_list = []

    # Create session with retry strategy
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # Load input JSON
    try:
        with open('link.json', 'r', encoding='utf-8') as f:
            channels = json.load(f)

        hash_code = os.environ.get('SECRET_HASH')
        if not hash_code:
            print("❌ Error: SECRET_HASH not found in environment.")
            return

    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Referer': 'https://google.com'
    }

    for channel in channels:
        try:
            site_url = channel.get('SiteUrl')
            if not site_url:
                continue

            print(f"\n🔎 Processing: {channel.get('name')}")

            res = session.get(site_url, headers=headers, timeout=20)
            res.raise_for_status()

            # ------------------------------------------
            # Detect page type and choose correct variable
            # ------------------------------------------
            if "alt.php" in site_url:
                pattern = r'(?:const|var|let)\s+decryptedData\s*=\s*["\'](.*?)["\']'
            elif "sports.php" in site_url:
                pattern = r'(?:const|var|let)\s+hi\s*=\s*["\'](.*?)["\']'
            else:
                print("⚠️ Unknown link type. Skipping.")
                continue

            match = re.search(pattern, res.text)

            if not match:
                print("❌ No matching JS variable found.")
                continue

            scraped_code = match.group(1)

            # Call your decrypt API
            vercel_url = f"https://e-rho-ivory.vercel.app/get?url={scraped_code}&key={hash_code}"
            api_res = session.get(vercel_url, headers=headers, timeout=20)
            api_res.raise_for_status()

            decrypted_str = api_res.json().get('decrypted', '')

            if not decrypted_str:
                print("❌ Decryption failed.")
                continue

            # ------------------------------------------
            # Parse decrypted response
            # ------------------------------------------
            parts = decrypted_str.split('!')
            if len(parts) < 3:
                print("❌ Invalid decrypted format.")
                continue

            kid_list = [k.strip() for k in parts[0].split(',')]
            key_list = [k.strip() for k in parts[1].split(',')]
            extracted_url = parts[2]

            clearkeys_map = dict(zip(kid_list, key_list))

            # ------------------------------------------
            # Build final entry
            # ------------------------------------------
            if ".m3u8" in extracted_url:
                entry = {
                    "id": channel.get('id'),
                    "name": channel.get('name'),
                    "logo": channel.get('logo'),
                    "streamUrl": extracted_url,
                    "quality": channel.get('quality')
                }
            else:
                entry = {
                    "id": channel.get('id'),
                    "name": channel.get('name'),
                    "logo": channel.get('logo'),
                    "mpdUrl": extracted_url,
                    "quality": channel.get('quality'),
                    "drm": {"clearKeys": clearkeys_map}
                }

            final_list.append(entry)
            print(f"✅ Success: {channel.get('name')}")

            # Prevent site blocking
            time.sleep(2)

        except Exception as e:
            print(f"❌ Error on {channel.get('id')}: {e}")

    # ------------------------------------------
    # Save output file
    # ------------------------------------------
    output_data = {"channels": final_list}

    with open('final.json', 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=4, ensure_ascii=False)

    print(f"\n🎉 Completed! {len(final_list)} channels saved to final.json")


if __name__ == "__main__":
    process_links()
