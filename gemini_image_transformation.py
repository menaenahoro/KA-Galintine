#!/usr/bin/env python3
"""
Gemini Image Transformer — Google Drive Edition
=================================================
Lists images in a Google Drive folder, transforms each one using
Gemini 1.5 Pro + Imagen 3, and uploads the result back to the same
folder with a _transformed suffix.

Requirements:
    pip install google-genai google-auth google-auth-oauthlib google-api-python-client pillow

Usage:
    python gemini_image_transform.py --folder-id DRIVE_FOLDER_ID \\
        --prompt "Turn into a watercolor painting"

How to get your folder ID:
    Open the folder in Google Drive in your browser.
    The URL looks like: https://drive.google.com/drive/folders/1ABC...XYZ
    The long string after /folders/ is your folder ID.

API Keys needed:
    1. GEMINI_API_KEY   — https://aistudio.google.com/app/apikey
    2. Google OAuth credentials (credentials.json) — see SETUP below

SETUP (one time):
    1. Go to https://console.cloud.google.com
    2. Create a project → Enable "Google Drive API"
    3. Go to APIs & Services → Credentials → Create OAuth 2.0 Client ID
       (Application type: Desktop app)
    4. Download the JSON and save it as credentials.json in this folder
    5. On first run the browser will open for you to authorize access
       and token.json will be saved automatically for future runs.
"""

import os
import sys
import io
import base64
import argparse
import logging
import tempfile
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
# ── Install dependencies if missing ──────────────────────────────────────────
REQUIRED = ["google-genai", "google-auth", "google-auth-oauthlib",
            "google-api-python-client", "pillow"]

try:
    from google import genai
    from google.genai import types
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from PIL import Image
except ImportError:
    # print("Installing required packages...")
    os.system(f"{sys.executable} -m pip install {' '.join(REQUIRED)} --quiet")
    from google import genai
    from google.genai import types
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from PIL import Image

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

# ── Google Drive OAuth scopes ─────────────────────────────────────────────────
SCOPES = ["https://www.googleapis.com/auth/drive"]

# ── Supported MIME types in Google Drive ─────────────────────────────────────
IMAGE_MIME_TYPES = {
    "image/jpeg", "image/png", "image/webp",
    "image/gif", "image/bmp", "image/tiff"
}

# ── Default prompt ────────────────────────────────────────────────────────────
DEFAULT_PROMPT = (
    "Transform this image into a vibrant watercolor painting. "
    "Preserve the composition and subjects but apply soft watercolor textures, "
    "gentle color bleeding, and artistic brush strokes."
)


# ─────────────────────────────────────────────────────────────────────────────
# Google Drive helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_drive_service(credentials_file: str = "credentials.json", token_file: str = "token.json"):
    """Authenticate and return a Google Drive service client."""
    creds = None

    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_file):
                # print(f"\n❌  {credentials_file} not found!")
                # print("    Follow the SETUP instructions at the top of this script.")
                # print("    Short version:")
                # print("    1. https://console.cloud.google.com → Enable Drive API")
                # print("    2. Create OAuth 2.0 Desktop credentials → Download JSON")
                # print(f"    3. Save as '{credentials_file}' next to this script\n")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_file, "w") as f:
            f.write(creds.to_json())
        log.info(f"Auth token saved to {token_file}")

    return build("drive", "v3", credentials=creds)


def list_images_in_folder(service, folder_id: str) -> list[dict]:
    """Return list of image file metadata dicts in the Drive folder."""
    query = (
        f"'{folder_id}' in parents "
        f"and mimeType contains 'image/' "
        f"and trashed = false"
    )
    results = []
    page_token = None

    while True:
        resp = service.files().list(
            q=query,
            spaces="drive",
            fields="nextPageToken, files(id, name, mimeType)",
            pageToken=page_token,
        ).execute()
        results.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    # Filter to supported types and exclude already-transformed files
    return [
        f for f in results
        if f["mimeType"] in IMAGE_MIME_TYPES
        and "_transformed" not in f["name"]
    ]


def download_image(service, file_id: str) -> bytes:
    """Download a Drive file and return its bytes."""
    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue()


def upload_image(service, image_bytes: bytes, filename: str, parent_folder_id: str) -> str:
    """Upload image bytes to Drive folder. Returns the new file's ID."""
    metadata = {"name": filename, "parents": [parent_folder_id]}
    media = MediaIoBaseUpload(io.BytesIO(image_bytes), mimetype="image/jpeg", resumable=True)
    file = service.files().create(
        body=metadata,
        media_body=media,
        fields="id, name"
    ).execute()
    return file.get("id")


def already_transformed(service, folder_id: str, transformed_name: str) -> bool:
    """Check if a transformed version already exists in the folder."""
    query = (
        f"'{folder_id}' in parents "
        f"and name = '{transformed_name}' "
        f"and trashed = false"
    )
    resp = service.files().list(q=query, fields="files(id)").execute()
    return len(resp.get("files", [])) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Gemini helpers
# ─────────────────────────────────────────────────────────────────────────────

def normalise_to_jpeg(raw_bytes: bytes) -> bytes:
    """Convert any image format to JPEG bytes via PIL."""
    with Image.open(io.BytesIO(raw_bytes)) as img:
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=92)
        return buf.getvalue()


def build_imagen_prompt(gemini_client: genai.Client, image_bytes: bytes, user_prompt: str) -> str:
    """Use gemini-1.5-pro to craft a rich Imagen generation prompt."""
    log.info("  🧠  Crafting generation prompt with gemini-1.5-pro ...")

    instruction = (
        f"You are a prompt engineer for an AI image generation model.\n"
        f"Look at this image carefully and write a single, detailed image-generation prompt "
        f"that will produce a NEW version of it according to this instruction:\n\n"
        f"  \"{user_prompt}\"\n\n"
        f"Your prompt must:\n"
        f"- Describe the transformed scene in full (subjects, setting, lighting, colours, style)\n"
        f"- Incorporate the specific artistic/stylistic change requested\n"
        f"- Be a single paragraph of 40-80 words\n"
        f"- NOT use words like 'transform', 'convert', or 'the original image'\n"
        f"Return ONLY the prompt text, nothing else."
    )

    response = gemini_client.models.generate_content(
        model="gemini-1.5-pro",
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            instruction,
        ],
    )
    prompt_text = response.text.strip()
    log.info(f"  💬  Imagen prompt: {prompt_text[:100]}...")
    return prompt_text


def generate_transformed_image(
    gemini_client: genai.Client,
    imagen_prompt: str,
    source_image_bytes: bytes,
    ref_image_bytes: bytes,
) -> bytes | None:
    # """Generate a new image via Imagen 3, with gemini-2.0-flash fallback."""

    # # ── Imagen 3 ──────────────────────────────────────────────────────────────
    # log.info("  🎨  Generating with Imagen 3 ...")
    # try:
    #     response = gemini_client.models.generate_images(
    #         model="imagen-3.0-generate-002",
    #         prompt=imagen_prompt,
    #         config=types.GenerateImagesConfig(
    #             number_of_images=1,
    #             aspect_ratio="1:1",
    #             safety_filter_level="block_only_high",
    #             person_generation="allow_adult",
    #         ),
    #     )
    #     if response.generated_images:
    #         data = response.generated_images[0].image.image_bytes
    #         if isinstance(data, str):
    #             data = base64.b64decode(data)
    #         return data
    # except Exception as e:
    #     log.warning(f"  ⚠️   Imagen 3 unavailable: {e}")
    #     log.warning("       Falling back to gemini-2.0-flash-exp-image-generation ...")

    # ── Fallback ──────────────────────────────────────────────────────────────
    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.0-flash-exp-image-generation",
            contents=[
                imagen_prompt,
                types.Part.from_bytes(data=source_image_bytes, mime_type="image/jpeg"),
                types.Part.from_bytes(data=ref_image_bytes, mime_type="image/jpeg"),
            ],
            config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
        )
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                data = part.inline_data.data
                if isinstance(data, str):
                    data = base64.b64decode(data)
                return data
    except Exception as e:
        log.error(f"  ❌  Fallback generation failed: {e}")

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────────────────────────────────────

def process_file(
    drive_service,
    gemini_client: genai.Client,
    file_meta: dict,
    source_folder_id: str,
    ref_folder_id: str,
    user_prompt: str,
    suffix: str,
    skip_existing: bool,
) -> bool:
    # """Download → transform → upload one image. Returns True on success."""
    # name = file_meta["name"]
    # file_id = file_meta["id"]
    # stem = Path(name).stem
    # transformed_name = f"{stem}{suffix}.jpg"

    # if skip_existing and already_transformed(drive_service, folder_id, transformed_name):
    #     log.info(f"  ⏭️   Skipping (already exists): {transformed_name}")
    #     return True

    try:
        # 1. Download
        log.info(f"  ⬇️   Downloading from Drive ...")
        raw_bytes = download_image(drive_service, file_id)
        image_bytes = normalise_to_jpeg(raw_bytes)

        # # 2. Build prompt with gemini-1.5-pro
        # imagen_prompt = build_imagen_prompt(gemini_client, image_bytes, user_prompt)

        # 3. Generate transformed image
        transformed_bytes = generate_transformed_image(gemini_client, imagen_prompt, image_bytes)
        if not transformed_bytes:
            log.error(f"  ❌  No image generated for {name}")
            return False

        # 4. Upload back to same Drive folder
        log.info(f"  ⬆️   Uploading '{transformed_name}' to Drive ...")
        new_id = upload_image(drive_service, transformed_bytes, transformed_name, folder_id)
        log.info(f"  ✅  Done — Drive file ID: {new_id}")
        return True

    except Exception as e:
        log.error(f"  ❌  Error processing '{name}': {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Transform Google Drive images with Gemini 1.5 Pro + Imagen 3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Transform all images in a Drive folder (watercolor default)
  python gemini_image_transform.py --folder-id 1ABCdef_XYZ

  # Custom style
  python gemini_image_transform.py --folder-id 1ABCdef_XYZ \\
    --prompt "Convert to a retro 80s neon synthwave poster"

  # Only first 5 images, skip already-transformed ones
  python gemini_image_transform.py --folder-id 1ABCdef_XYZ \\
    --limit 5 --skip-existing

How to find your folder ID:
  Open the folder in Google Drive → the URL ends with /folders/<FOLDER_ID>

Environment:
  GEMINI_API_KEY   Your Google AI Studio API key (required)
                   Get one at: https://aistudio.google.com/app/apikey
        """,
    )
    parser.add_argument("--folder-id",    "-f", required=True,          help="Google Drive folder ID")
    parser.add_argument("--prompt",       "-p", default=DEFAULT_PROMPT, help="Transformation instruction")
    parser.add_argument("--suffix",       "-s", default="_transformed", help="Suffix for output filenames")
    parser.add_argument("--limit",        "-n", type=int,               help="Max images to process")
    parser.add_argument("--skip-existing",      action="store_true",    help="Skip already-transformed images")
    parser.add_argument("--credentials",        default="credentials.json", help="Path to OAuth credentials JSON")
    parser.add_argument("--token",              default="token.json",   help="Path to save/load OAuth token")

    args = parser.parse_args()

    # ── Gemini client ─────────────────────────────────────────────────────────
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        # print("\n❌  GEMINI_API_KEY not set!")
        # print("    Get a free key at: https://aistudio.google.com/app/apikey")
        # print("    Then run: export GEMINI_API_KEY='your-key-here'\n")
        sys.exit(1)
    gemini_client = genai.Client(api_key=api_key)

    # ── Drive client ──────────────────────────────────────────────────────────
    log.info("Authenticating with Google Drive ...")
    drive_service = get_drive_service(args.credentials, args.token)

    # ── List images ───────────────────────────────────────────────────────────
    log.info(f"Scanning folder: {args.folder_id}")
    images = list_images_in_folder(drive_service, args.folder_id)

    if not images:
        log.warning("No images found in the specified Drive folder.")
        sys.exit(0)

    if args.limit:
        images = images[: args.limit]

    log.info(f"Found {len(images)} image(s) to process")
    log.info(f"Prompt: \"{args.prompt[:80]}{'...' if len(args.prompt) > 80 else ''}\"")
    log.info(f"Transformed files will be uploaded with suffix '{args.suffix}'")
    # print()

    # ── Process ───────────────────────────────────────────────────────────────
    ok = 0
    for idx, file_meta in enumerate(images, 1):
        log.info(f"[{idx}/{len(images)}] {file_meta['name']}")
        if process_file(
            drive_service, gemini_client,
            file_meta, args.folder_id,
            args.prompt, args.suffix, args.skip_existing
        ):
            ok += 1
        # print()

    # ── Summary ───────────────────────────────────────────────────────────────
    # print("=" * 52)
    log.info(f"Done -- {ok}/{len(images)} image(s) transformed and uploaded to Drive.")
    if ok < len(images):
        log.warning(f"{len(images) - ok} failed. Re-run with --skip-existing to retry only failed ones.")


if __name__ == "__main__":
    main()