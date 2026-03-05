import base64
import io
import os
import json
import sys
import tempfile
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from dotenv import load_dotenv
import re
import unicodedata

FOLDER_ID_TO_UPLOAD_PROCESSED = '1DRPuoozcDq6y6Ygeum_zbBK9pHTCm9b4'
FOLDER_ID_FOR_UNPROCESSED = "14Sat-oN1mqbZq8o_A1mwXTiJ02iEeJT8"
_BASE_DIR = Path(os.environ.get("GITHUB_WORKSPACE", Path(__file__).parent)).resolve()

DIR_UNPROCESSED = _BASE_DIR / "downloads" / "unprocessed"   # user submitted images
DIR_STYLES      = _BASE_DIR / "downloads" / "styles"        # style references (cached)
DIR_OUTPUTS     = _BASE_DIR / "outputs"  

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
    from google.auth.exceptions import RefreshError

    from PIL import Image
except ImportError:
    print("Installing required packages...")
    os.system(f"{sys.executable} -m pip install {' '.join(REQUIRED)} --quiet")
    from google import genai
    from google.genai import types
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.exceptions import RefreshError

    from PIL import Image

load_dotenv()


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


GOOGLE_DRIVE_FILES = {
    "Ghana-Must-Stay": {
        "folder_id": "1GFWQXi1DCQgj5rz3yMqbwpHdshTKtO8S",
        "pictures": ["A1.jpg", "A2.jpg", "A3.jpg", "A4.png", "A5.jpg", "A6.jpg", "A7.png"],
        "videos": ["A8.mp4"],
    },
    "Sisi Eko Sensation": {
        "folder_id": "1gxieDKtvTdJ3sHyhjOCCdF0qG4p0--5K",
        "pictures": ["B1.jpg", "B2.jpg", "B3.jpg", "B4.png", "B5.jpg", "B6.png", "B7.png"],
        "videos": ["B8.mp4", "B9.mp4"],
    },
    "Ileke All Back": {
        "folder_id": "19GCAuXf6kbj0jRC0q0QemnnWVJA_7rP2",
        "pictures": ["C1.jpg", "C2.png", "C3.png", "C4.jpg", "C5.jpg", "C6.png", "C8.png"],
        "videos": ["C7.mp4"],
    },
    "Slicker than your Average": {
        "folder_id": "1OUBzXFckw6q-QK-jfooYCf3Ws_KmNDsJ",
        "pictures": ["D1.JPG", "D2.jpg", "D3.jpg", "D4.jpg", "D5.jpg", "D6.jpg", "D7.jpg", "D8.jpg", "D9.jpg", "D10.jpg", "D11.jpg"],
        "videos": [],
    },
    "The Big Steppa": {
        "folder_id": "1Q4_p85mV4ieVsP1QN1y96U-GUIaQMqxW",
        "pictures": ["E1.jpg", "E2.jpg", "E3.jpg", "E4.jpg", "E5.jpg", "E6.jpg", "E7.jpg", "E8.jpg"],
        "videos": ["E9.mp4", "E10.mp4"],
    },
    "Long-Term Investment": {
        "folder_id": "1-3hdbeQ-RezykFWRXrQfj-lQ_PRMXXMg",
        "pictures": ["F1.jpg", "F2.jpg", "F3.jpg", "F4.jpg", "F5.jpg", "F6.jpg", "F7.jpg", "F8.jpg"],
        "videos": ["F9.mp4", "F10.mp4"],
    },
    "Gara Gara Girlie": {
        "folder_id": "1n2UVvOaBjC5WhNUuBpNOAhsJf0yWdDkQ",
        "pictures": ["G1.jpg", "G2.jpg", "G3.jpg", "G4.jpg", "G5.jpg", "G6.jpg", "G7.jpg", "G8.jpg", "G9.jpg"],
        "videos": ["G10.mp4"],
    },
    "I woke up like this": {
        "folder_id": "1-P6JJTtGgR17u5agy-xLHORtyvuhuIjK",
        "pictures": ["H1.jpg", "H2.jpg", "H3.jpg", "H4.jpg", "H5.jpg", "H6.jpg", "H7.jpg", "H8.jpg", "H9.jpg"],
        "videos": ["H10.mp4", "H11.mp4"],
    },
    "Clap for the Queen": {
        "folder_id": "1n2UVvOaBjC5WhNUuBpNOAhsJf0yWdDkQ",
        "pictures": ["I1.jpg", "I2.jpg", "I3.jpg", "I4.jpg", "I5.jpg", "I6.jpg", "I7.jpg", "I8.jpg", "I9.jpg"],
        "videos": ["I10.mp4"],
    },
    "Basket Case": {
        "folder_id": "1qSU9Vk_Uvg9oy-EInTe2QK_5Mw33shnY",
        "pictures": ["J1.jpg", "J2.jpg", "J3.jpg", "J4.jpg", "J5.jpg", "J6.jpg", "J7.jpg", "J8.jpg", "J9.jpg"],
        "videos": ["J10.mp4"],
    },
    "Woop! Woop!": {
        "folder_id": "1GUOlp39jqNzCzxNa20VZ4s9BVLYR19jr",
        "pictures": ["K1.jpg", "K2.jpg", "K3.jpg", "K4.jpg", "K5.jpg", "K6.jpg", "K7.jpg", "K8.jpg"],
        "videos": ["K9.mp4"],
    },
    "Shuku-Shuku Bam-Bam": {
        "folder_id": "15H7rnpsWsD07F3Nnjmm33juh3BnPWVkn",
        "pictures": ["L1.jpg", "L2.jpg", "L3.jpg", "L4.jpg", "L5.jpg", "L6.jpg", "L7.jpg", "L8.jpg"],
        "videos": ["L9.mp4", "L10.mp4"],
    },
}

# ── Sheet column indices (based on header row) ────────────────────────────────
COL_NAME   = 0
COL_EMAIL  = 1
COL_FILE   = 2
COL_STYLE  = 3
COL_STATUS = 4



google_drive_files = {
    "Ghana-Must-Stay": {
        "folder_id": "1GFWQXi1DCQgj5rz3yMqbwpHdshTKtO8S",
        "pictures": ["A1.jpg", "A2.jpg", "A3.jpg", "A4.png", "A5.jpg", "A6.jpg", "A7.png"],
        "videos": ["A8.mp4"],
    },

    "Sisi Eko Sensation": {
        "folder_id": "1gxieDKtvTdJ3sHyhjOCCdF0qG4p0--5K",
        "pictures": ["B1.jpg", "B2.jpg", "B3.jpg", "B4.png", "B5.jpg", "B6.png", "B7.png"],
        "videos": ["B8.mp4", "B9.mp4"],
    },

    "Ileke All Back": {
        "folder_id": "19GCAuXf6kbj0jRC0q0QemnnWVJA_7rP2",
        "pictures": ["C1.jpg", "C2.png", "C3.png", "C4.jpg", "C5.jpg", "C6.png", "C8.png"],
        "videos": ["C7.mp4"],
    },

    "Slicker than your Average": {
        "folder_id": "1OUBzXFckw6q-QK-jfooYCf3Ws_KmNDsJ",
        "pictures": ["D1.JPG", "D2.jpg", "D3.jpg", "D4.jpg", "D5.jpg", "D6.jpg", "D7.jpg", "D8.jpg", "D9.jpg", "D10.jpg", "D11.jpg"],
        "videos": [],
    },

    "The Big Steppa": {
        "folder_id": "1Q4_p85mV4ieVsP1QN1y96U-GUIaQMqxW",
        "pictures": ["E1.jpg", "E2.jpg", "E3.jpg", "E4.jpg", "E5.jpg", "E6.jpg", "E7.jpg", "E8.jpg"],
        "videos": ["E9.mp4", "E10.mp4"],
    },

    "Long-Term Investment": {
        "folder_id": "1-3hdbeQ-RezykFWRXrQfj-lQ_PRMXXMg",
        "pictures": ["F1.jpg", "F2.jpg", "F3.jpg", "F4.jpg", "F5.jpg", "F6.jpg", "F7.jpg", "F8.jpg"],
        "videos": ["F9.mp4", "F10.mp4"],
    },

    "Gara Gara Girlie": {
        "folder_id": "1n2UVvOaBjC5WhNUuBpNOAhsJf0yWdDkQ",
        "pictures": ["G1.jpg", "G2.jpg", "G3.jpg", "G4.jpg", "G5.jpg", "G6.jpg", "G7.jpg", "G8.jpg", "G9.jpg"],
        "videos": ["G10.mp4"],
    },

    "I woke up like this": {
        "folder_id": "1-P6JJTtGgR17u5agy-xLHORtyvuhuIjK",
        "pictures": ["H1.jpg", "H2.jpg", "H3.jpg", "H4.jpg", "H5.jpg", "H6.jpg", "H7.jpg", "H8.jpg", "H9.jpg"],
        "videos": ["H10.mp4", "H11.mp4"],
    },

    "Clap for the Queen": {
        "folder_id": "1n2UVvOaBjC5WhNUuBpNOAhsJf0yWdDkQ",
        "pictures": ["I1.jpg", "I2.jpg", "I3.jpg", "I4.jpg", "I5.jpg", "I6.jpg", "I7.jpg", "I8.jpg", "I9.jpg"],
        "videos": ["I10.mp4"],
    },

    "Basket Case": {
        "folder_id": "1qSU9Vk_Uvg9oy-EInTe2QK_5Mw33shnY",
        "pictures": ["J1.jpg", "J2.jpg", "J3.jpg", "J4.jpg", "J5.jpg", "J6.jpg", "J7.jpg", "J8.jpg", "J9.jpg"],
        "videos": ["J10.mp4"],
    },

    "Woop! Woop!": {
        "folder_id": "1GUOlp39jqNzCzxNa20VZ4s9BVLYR19jr",
        "pictures": ["K1.jpg", "K2.jpg", "K3.jpg", "K4.jpg", "K5.jpg", "K6.jpg", "K7.jpg", "K8.jpg"],
        "videos": ["K9.mp4"],
    },

    "Shuku-Shuku Bam-Bam": {
        "folder_id": "15H7rnpsWsD07F3Nnjmm33juh3BnPWVkn",
        "pictures": ["L1.jpg", "L2.jpg", "L3.jpg", "L4.jpg", "L5.jpg", "L6.jpg", "L7.jpg", "L8.jpg"],
        "videos": ["L9.mp4", "L10.mp4"],
    },
}


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"\n❌ Environment variable '{name}' is not set!")
        sys.exit(1)
    return value

def get_google_credentials():
    creds = None
    token_json = os.getenv("GOOGLE_TOKEN_JSON")

    # Load cached token from env
    if token_json:
        try:
            creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
        except Exception as e:
            print(f"⚠️ Could not load GOOGLE_TOKEN_JSON: {e}")
            creds = None

    # Refresh if possible
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            # print updated token after successful refresh
            print("\n" + "=" * 60)
            print("✅ Token refreshed! Save this as your GOOGLE_TOKEN_JSON env var:")
            print("=" * 60)
            print(creds.to_json())
            print("=" * 60 + "\n")
            return creds
        except RefreshError as e:
            print(f"⚠️ Token refresh failed: {e}")
            print("⚠️ Existing GOOGLE_TOKEN_JSON is stale or has wrong scopes. Re-authenticating...")
            creds = None

    # Fresh login if missing / invalid / refresh failed
    if not creds or not creds.valid:
        creds_data = _require_env("GOOGLE_CREDENTIALS_JSON")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            tmp.write(creds_data)
            tmp_path = tmp.name

        try:
            flow = InstalledAppFlow.from_client_secrets_file(tmp_path, SCOPES)
            creds = flow.run_local_server(port=0)
        finally:
            os.unlink(tmp_path)

        print("\n" + "=" * 60)
        print("✅ Auth successful! Save this as your GOOGLE_TOKEN_JSON env var:")
        print("=" * 60)
        print(creds.to_json())
        print("=" * 60 + "\n")

    return creds

def get_sheets_service():
    creds = get_google_credentials()
    return build("sheets", "v4", credentials=creds)

def get_drive_service():
    creds = get_google_credentials()
    return build("drive", "v3", credentials=creds)

def strip_emojis(text: str) -> str:
    """Remove all emoji and non-ASCII decorative characters from a string."""
    # Remove anything in Unicode categories: So (Symbol, other), Sm, Sk, No, etc.
    cleaned = "".join(
        ch for ch in text
        if not unicodedata.category(ch).startswith("S")   # symbols
        and not unicodedata.category(ch).startswith("C")  # control / format chars
    )
    # Also strip flag emoji sequences (regional indicator letters U+1F1E6–1F1FF)
    cleaned = re.sub(r'[\U0001F1E0-\U0001F1FF]', '', cleaned)
    return cleaned.strip()

def read_all(
    service,
    spreadsheet_id: str,
    sheet_name: str = "Sheet1",
    as_dicts: bool = False,
):
    """
    Read all rows from a sheet tab.

    - as_dicts=False -> returns raw list[list]
    - as_dicts=True  -> returns list[dict] with _row_number included
    """
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=sheet_name,
    ).execute()

    rows = result.get("values", [])

    if not as_dicts:
        return rows

    if not rows:
        return []

    header = rows[0]

    output = []
    for sheet_row_num, row in enumerate(rows[1:], start=2):  # row 1 is header
        item = {
            col: row[i] if i < len(row) else None
            for i, col in enumerate(header)
        }
        item["_row_number"] = sheet_row_num
        output.append(item)

    return output


def col_to_letter(col_num: int) -> str:
    """
    Convert 1-based column number to Sheets column letter.
    1 -> A, 2 -> B, 27 -> AA
    """
    result = ""
    while col_num > 0:
        col_num, remainder = divmod(col_num - 1, 26)
        result = chr(65 + remainder) + result
    return result


def update_status_by_identity(
    service,
    sheet_name: str,
    *,
    name: str,
    email: str,
    file: str,
    style: str,
    status_value: str = "processed",
    spreadsheet_id='1chGGVMDcoL_9OO69rsqemXlvN389oyCKQG74wq-QB5o'
):
    """
    Find the row matching name + email + file + style,
    then update its status column.
    """
    raw_rows = read_all(service, spreadsheet_id, sheet_name, as_dicts=False)
    if not raw_rows:
        raise ValueError("Sheet is empty.")

    header = raw_rows[0]

    required_cols = ["name", "email", "file", "style", "status"]
    for col in required_cols:
        if col not in header:
            raise ValueError(f"Missing required column: '{col}'")

    status_col_index = header.index("status") + 1  # 1-based
    status_col_letter = col_to_letter(status_col_index)

    rows = read_all(service, spreadsheet_id, sheet_name, as_dicts=True)

    for row in rows:
        if (
            row.get("name") == name
            and row.get("email") == email
            and row.get("file") == file
            and row.get("style") == style
        ):
            row_number = row["_row_number"]
            cell = f"{sheet_name}!{status_col_letter}{row_number}"
            update_cell(service, spreadsheet_id, cell, status_value)
            print(f"✅ Updated row {row_number} status -> {status_value}")
            return row_number

    raise ValueError(
        f"No matching row found for "
        f"name={name}, email={email}, file={file}, style={style}"
    )

def read_range(service, spreadsheet_id: str, cell_range: str) -> list[list]:
    """
    Read a specific range, e.g. 'Sheet1!A1:C10'
    Returns a 2D list (rows × columns).
    """
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=cell_range,
    ).execute()
    return result.get("values", [])


def write_rows(service, spreadsheet_id: str, cell_range: str, rows: list[list]):
    """
    Overwrite a range with new data.
    rows = [[row1col1, row1col2], [row2col1, row2col2], ...]
    """
    body = {"values": rows}
    result = service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=cell_range,
        valueInputOption="USER_ENTERED",   # interprets formulas & dates
        body=body,
    ).execute()
    print(f"  Updated {result.get('updatedCells')} cell(s)")


def append_rows(service, spreadsheet_id: str, sheet_name: str, rows: list[list]):
    """
    Append rows after the last row that has data.
    Useful for logging or adding new entries without knowing the current size.
    """
    body = {"values": rows}
    result = service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=sheet_name,
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",    # always adds new rows, never overwrites
        body=body,
    ).execute()
    updated = result.get("updates", {}).get("updatedRange")
    print(f"  Appended rows → {updated}")


def update_cell(service, spreadsheet_id: str, cell: str, value):
    """Update a single cell, e.g. cell='Sheet1!B3'"""
    write_rows(service, spreadsheet_id, cell, [[value]])


def clear_range(service, spreadsheet_id: str, cell_range: str):
    """Clear all values in a range without deleting the rows."""
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=cell_range,
    ).execute()
    print(f"  Cleared range: {cell_range}")


def get_sheet_names(service, spreadsheet_id: str) -> list[str]:
    """Return the names of all tabs/sheets in the spreadsheet."""
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return [s["properties"]["title"] for s in meta.get("sheets", [])]


def list_files_in_folder2(drive_service, folder_id: str) -> dict[str, str]:
    """Return {filename: file_id} for all files in a Drive folder."""
    query = f"'{folder_id}' in parents and trashed = false"
    results = {}
    page_token = None

    while True:
        resp = drive_service.files().list(
            q=query,
            fields="nextPageToken, files(id, name)",
            pageToken=page_token,
        ).execute()
        for f in resp.get("files", []):
            results[f["name"]] = f["id"]
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    return results

def list_files_in_folder(service, folder_id: str) -> list[dict]:
    """List all files inside a Drive folder."""
    query = f"'{folder_id}' in parents and trashed = false"
    results = []
    page_token = None

    while True:
        resp = service.files().list(
            q=query,
            fields="nextPageToken, files(id, name, mimeType, size)",
            pageToken=page_token,
        ).execute()

        results.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    return results


def download_file(service, file_id: str, save_path: str):
    """Download a file from Drive by its file ID."""
    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)

    done = False
    while not done:
        status, done = downloader.next_chunk()
        print(f"  Download progress: {int(status.progress() * 100)}%")

    with open(save_path, "wb") as f:
        f.write(buf.getvalue())
    print(f"  Saved to: {save_path}")


def download_file_buffer(service, file_id: str) -> bytes:
    """Download a Drive file and return its bytes."""
    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue()

def normalise_to_jpeg(raw_bytes: bytes) -> bytes:
    """Convert any image format to JPEG bytes via PIL."""
    with Image.open(io.BytesIO(raw_bytes)) as img:
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=92)
        return buf.getvalue()
    
def return_normalised_image(drive_service, file_id):
        raw_bytes = download_file_buffer(drive_service, file_id)
        return normalise_to_jpeg(raw_bytes)



def upload_file(service, local_path: str, drive_folder_id: str, mime_type: str = "application/octet-stream") -> str:
    """Upload a local file to a Drive folder. Returns the new file's Drive ID."""
    filename = Path(local_path).name
    metadata = {"name": filename, "parents": [drive_folder_id]}

    with open(local_path, "rb") as f:
        media = MediaIoBaseUpload(f, mimetype=mime_type, resumable=True)
        file = service.files().create(
            body=metadata,
            media_body=media,
            fields="id, name"
        ).execute()

    print(f"  Uploaded '{filename}' → Drive ID: {file['id']}")
    return file["id"]


def upload_bytes(service, data: bytes, filename: str, drive_folder_id: str, mime_type: str = "image/jpeg") -> str:
    """Upload raw bytes to Drive (useful when you don't have a local file)."""
    metadata = {"name": filename, "parents": [drive_folder_id]}
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype=mime_type, resumable=True)
    file = service.files().create(
        body=metadata,
        media_body=media,
        fields="id, name"
    ).execute()
    print(f"  Uploaded '{filename}' → Drive ID: {file['id']}")
    return file["id"]


def delete_file(service, file_id: str):
    """Move a file to trash."""
    service.files().delete(fileId=file_id).execute()
    print(f"  Deleted file ID: {file_id}")




def get_unprocessed_rows(service) -> list[dict]:

    SPREADSHEET_ID = "1chGGVMDcoL_9OO69rsqemXlvN389oyCKQG74wq-QB5o"
    # ─────────────────────────────────────────────────────────────────────────

    # List all sheet tabs
    print("📋 Sheet tabs in this spreadsheet:")
    tabs = get_sheet_names(service, SPREADSHEET_ID)
    for tab in tabs:
        print(f"   - {tab}")
    print()

    # Use the first tab for all examples below
    tab = tabs[0] if tabs else "Sheet1"

    # Read all data
    print(f"📖 All data in '{tab}':")
    rows = read_all(service, SPREADSHEET_ID, tab)
    if not rows:
        print("  (sheet is empty)")
        result = []
    else:
        print('ROWS:', rows)
        header = rows[0]
        status_index = header.index("status")

        result = [header] + [
            row
            for row in rows[1:]
            if (
                len(row) <= status_index
                or row[status_index] is None
                or str(row[status_index]).strip() == ""
            )
        ]

        print('RESULT:', result)
    return result


def match_style_key(row_style: str, google_drive_files: dict) -> tuple[str, dict]:
    """
    Match a sheet style like:
      'Ghana-Must-Stay 🇬🇭'
      'Sisi Eko Sensation 🌀'
    to a google_drive_files key like:
      'Ghana-Must-Stay'
      'Sisi Eko Sensation'

    Strategy:
    - exact match first
    - then prefix match (so appended emoji/text still works)
    - case-insensitive
    """
    if not row_style or not str(row_style).strip():
        raise ValueError("Row style is empty.")

    style_text = str(row_style).strip()
    style_lower = style_text.casefold()

    # Exact match first
    for key, info in google_drive_files.items():
        if style_lower == key.strip().casefold():
            return key, info

    # Prefix match (handles emojis / trailing decorations)
    # Sort longest first to avoid accidental shorter-prefix matches
    for key in sorted(google_drive_files.keys(), key=len, reverse=True):
        if style_lower.startswith(key.strip().casefold()):
            return key, google_drive_files[key]

    raise ValueError(f"No matching style found for row style: {row_style}")

def get_cell(row: list, index: int, default=None):
    return row[index] if index < len(row) else default


def is_blank(value) -> bool:
    return value is None or str(value).strip() == ""

def build_pending_jobs(rows: list[list], google_drive_files: dict) -> list[dict]:
    """
    Convert raw sheet rows into structured pending jobs.

    Only returns rows where status is blank / missing.
    """
    if not rows:
        return []

    header = rows[0]

    required = ["name", "email", "file", "style"]
    for col in required:
        if col not in header:
            raise ValueError(f"Missing required column '{col}' in sheet header.")

    name_index = header.index("name")
    email_index = header.index("email")
    file_index = header.index("file")
    style_index = header.index("style")
    status_index = header.index("status") if "status" in header else None

    jobs = []

    for row_number, row in enumerate(rows[1:], start=2):
        status_value = get_cell(row, status_index) if status_index is not None else None

        # Skip already processed rows
        if not is_blank(status_value):
            continue

        name = get_cell(row, name_index)
        email = get_cell(row, email_index)
        file_name = get_cell(row, file_index)
        style_value = get_cell(row, style_index)

        matched_style_key, style_info = match_style_key(style_value, google_drive_files)

        jobs.append({
            "row_number": row_number,
            "name": name,
            "email": email,
            "file": file_name,
            "style": style_value,
            "matched_style_key": matched_style_key,
            "style_folder_id": style_info["folder_id"],
            "style_pictures": style_info.get("pictures", []),
            "style_videos": style_info.get("videos", []),
        })

    return jobs


def list_files_map_by_name(service, folder_id: str) -> dict[str, dict]:
    """
    Build a {filename: file_metadata} map for a Drive folder.
    """
    files = list_files_in_folder(service, folder_id)
    return {f["name"]: f for f in files}

def match_style(raw_style: str) -> tuple[str, dict] | tuple[None, None]:
    """
    Match a raw style string (possibly containing emojis) to GOOGLE_DRIVE_FILES.

    Returns (matched_key, style_dict) or (None, None) if no match.

    Strategy:
      1. Strip emojis from raw_style → clean_style
      2. Exact match (case-insensitive)
      3. Partial / starts-with match as fallback
    """
    clean_style = strip_emojis(raw_style).lower()

    # 1. Exact match
    for key, value in GOOGLE_DRIVE_FILES.items():
        if key.lower() == clean_style:
            print(f"  ✅ Style matched (exact): '{key}'")
            return key, value

    # 2. Partial match — raw style starts with or contains the key
    for key, value in GOOGLE_DRIVE_FILES.items():
        if clean_style.startswith(key.lower()) or key.lower() in clean_style:
            print(f"  ✅ Style matched (partial): '{key}' from '{raw_style}'")
            return key, value

    print(f"  ⚠️  No style match found for: '{raw_style}' (cleaned: '{clean_style}')")
    return None, None

def prepare_job_assets(
    drive_service,
    job: dict,
    unprocessed_folder_id: str,
) -> dict:
    """
    For one job:
    - find the source image in the unprocessed folder
    - find the style reference images in the style folder
    - download + normalise them to JPEG bytes
    """
    # Source file from unprocessed folder
    unprocessed_files = list_files_map_by_name(drive_service, unprocessed_folder_id)
    source_meta = unprocessed_files.get(job["file"])

    if not source_meta:
        raise FileNotFoundError(
            f"Source file '{job['file']}' not found in unprocessed folder {unprocessed_folder_id}"
        )

    source_image_bytes = return_normalised_image(drive_service, source_meta["id"])

    # Reference files from style folder
    style_files = list_files_map_by_name(drive_service, job["style_folder_id"])

    ref_image_bytes = []
    ref_file_ids = []
    ref_missing = []

    for picture_name in job["style_pictures"]:
        file_meta = style_files.get(picture_name)
        if not file_meta:
            ref_missing.append(picture_name)
            continue

        ref_file_ids.append(file_meta["id"])
        ref_image_bytes.append(return_normalised_image(drive_service, file_meta["id"]))

    return {
        **job,
        "source_file_id": source_meta["id"],
        "source_image_bytes": source_image_bytes,
        "ref_file_ids": ref_file_ids,
        "ref_image_bytes": ref_image_bytes,
        "missing_ref_pictures": ref_missing,
    }

# def generate_transformed_image(
#     gemini_client: genai.Client,
#     imagen_prompt: str,
#     source_image_bytes: bytes,
#     ref_image_bytes: list[bytes],
# ) -> bytes | None:
#     """
#     Generate a transformed image using:
#     - one source image
#     - one or more reference images
#     """

#     try:
#         contents = [
#             imagen_prompt,
#             types.Part.from_bytes(data=source_image_bytes, mime_type="image/jpeg"),
#         ]

#         # Add each reference image as its own Part
#         contents.extend(
#             types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
#             for img_bytes in ref_image_bytes
#         )

#         response = gemini_client.models.generate_content(
#             model="gemini-2.5-flash-image",
#             contents=contents,
#             config=types.GenerateContentConfig(
#                 response_modalities=["IMAGE", "TEXT"]
#             ),
#         )

#         for part in response.candidates[0].content.parts:
#             if part.inline_data and part.inline_data.mime_type.startswith("image/"):
#                 data = part.inline_data.data
#                 if isinstance(data, str):
#                     data = base64.b64decode(data)
#                 return data

#     except Exception as e:
#         print(f"❌ Fallback generation failed: {e}")

#     return None

def extract_image_from_response(response) -> bytes | None:
    """Pull the first image part out of a Gemini response."""
    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.mime_type.startswith("image/"):
            data = part.inline_data.data
            if isinstance(data, str):
                data = base64.b64decode(data)
            return data
    return None


# def generate_transformed_image(
#     gemini_client: genai.Client,
#     prompt: str,
#     source_image_bytes: bytes,
#     ref_image_bytes_list: list[bytes],
# ) -> bytes | None:
#     """
#     Identity-preserving style transfer using Gemini image editing.

#     Content order matters — model pays most attention to what comes first:
#       [prompt] → [user photo] → [ref1] → [ref2] → [ref3]

#     The prompt explicitly anchors the person's identity before the
#     style references are introduced, reducing drift.
#     """
#     print("  🎨  Generating styled image (identity-preserving) ...")

#     # ── Build contents: prompt → user photo → style references ───────────────
#     contents = [
#         prompt,
#         types.Part.from_bytes(data=source_image_bytes, mime_type="image/jpeg"),
#     ]
#     for ref_bytes in ref_image_bytes_list:
#         contents.append(types.Part.from_bytes(data=ref_bytes, mime_type="image/jpeg"))

#     # ── Attempt 1: gemini-2.0-flash-exp-image-generation ─────────────────────
#     try:
#         response = gemini_client.models.generate_content(
#             model="gemini-2.0-flash-exp-image-generation",
#             contents=contents,
#             config=types.GenerateContentConfig(
#                 response_modalities=["IMAGE", "TEXT"],
#             ),
#         )
#         result = extract_image_from_response(response)
#         if result:
#             return result
#         print("  ⚠️  Model returned no image — trying fallback model ...")

#     except Exception as e:
#         print(f"  ⚠️  gemini-2.0-flash-exp-image-generation failed: {e}")
#         print("       Trying gemini-2.5-flash-preview-05-20 ...")

#     # ── Attempt 2: gemini-2.5-flash (newer, better at following instructions) ─
#     try:
#         response = gemini_client.models.generate_content(
#             model="gemini-2.5-flash-preview-05-20",
#             contents=contents,
#             config=types.GenerateContentConfig(
#                 response_modalities=["IMAGE", "TEXT"],
#             ),
#         )
#         result = extract_image_from_response(response)
#         if result:
#             return result
#         print("  ⚠️  Fallback model also returned no image.")

#     except Exception as e:
#         print(f"  ❌  Both models failed: {e}")

#     return None

def load_image_bytes(local_path: Path) -> bytes:
    """Read a local image file as raw bytes."""
    return local_path.read_bytes()

def generate_transformed_image(
    gemini_client: genai.Client,
    prompt: str,
    source_image_path: Path,
    ref_image_paths: list[Path],
) -> bytes | None:
    """
    Read images from local paths and send to Gemini for style transfer.
    Content order: prompt → user photo → style references.
    """
    print(f"  🤖  Source image:  {source_image_path}")
    for p in ref_image_paths:
        print(f"  🤖  Reference:     {p}")

    contents = [
        prompt,
        Image.open(source_image_path).convert("RGB") # 
        # types.Part.from_bytes(data=load_image_bytes(source_image_path), mime_type="image/jpeg"),
    ]
    for ref_path in ref_image_paths:
        contents.append(
            Image.open(ref_path).convert("RGB")
                # types.Part.from_bytes(data=load_image_bytes(ref_path), mime_type="image/jpeg")
        )

    # # ── Attempt 1 ─────────────────────────────────────────────────────────────
    # print("  🎨  Generating (gemini-2.0-flash-exp-image-generation) ...")
    # try:
    #     response = gemini_client.models.generate_content(
    #         model="gemini-2.0-flash-exp-image-generation",
    #         contents=contents,
    #         config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
    #     )
    #     result = extract_image_from_response(response)
    #     if result:
    #         return result
    #     print("  ⚠️  No image in response — trying fallback ...")
    # except Exception as e:
    #     print(f"  ⚠️  Model 1 failed: {e} — trying fallback ...")

    # ── Attempt 2 ─────────────────────────────────────────────────────────────
    print("  🎨  Generating (gemini-3.1-flash-image-preview) ...")
    try:
        response = gemini_client.models.generate_content(
            # model="gemini-2.5-flash-image",
            model="gemini-3.1-flash-image-preview",
            # model="gemini-3.1-flash-image-preview",
            # model="gemini-3.1-flash-image-preview",
            contents=contents,
            config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
        )
        result = extract_image_from_response(response)
        if result:
            return result
        print("  ⚠️  Fallback also returned no image.")
    except Exception as e:
        print(f"  ❌  Both models failed: {e}")

    return None






def save_output_image(image_bytes: bytes, filename: str) -> Path:
    """Save transformed image bytes to the local outputs folder."""
    out_path = DIR_OUTPUTS / filename
    with Image.open(io.BytesIO(image_bytes)) as img:
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(out_path, "JPEG", quality=95)
    print(f"  💾  Saved locally → {out_path}")
    return out_path


def parse_rows(rows: list[list]) -> list[dict]:
    """
    Convert raw sheet rows into structured dicts, skipping the header row.
    Handles missing 'status' column gracefully.
    """
    if not rows:
        return []

    header = rows[0]
    records = []

    for i, row in enumerate(rows[1:], start=2):   # start=2 → actual sheet row number
        # Pad short rows
        while len(row) < COL_STATUS + 1:
            row.append("")

        record = {
            "row_index": i,
            "name":      row[COL_NAME].strip(),
            "email":     row[COL_EMAIL].strip(),
            "file":      row[COL_FILE].strip(),
            "style_raw": row[COL_STYLE].strip(),
            "status":    row[COL_STATUS].strip(),
        }
        records.append(record)

    return records

def download_to_local(drive_service, file_id: str, local_path: Path) -> Path:
    """
    Download a Drive file and save it as a normalised JPEG at local_path.
    Skips the download entirely if the file is already cached on disk.
    Returns the final local Path (always .jpg extension).
    """
    # Always resolve to .jpg since we normalise on save
    save_path = local_path.with_suffix(".jpg")

    if save_path.exists():
        print(f"    ✔  Cached: {save_path}")
        return save_path

    save_path.parent.mkdir(parents=True, exist_ok=True)

    # Download raw bytes from Drive
    request = drive_service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    # Normalise to JPEG and save
    with Image.open(io.BytesIO(buf.getvalue())) as img:
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(save_path, format="JPEG", quality=92)

    print(f"    ⬇️  Downloaded → {save_path}")
    return save_path


def upload_local_file_to_drive(drive_service, local_path: Path, folder_id: str) -> str:
    """Upload a local file to a Drive folder. Returns the new Drive file ID."""
    with open(local_path, "rb") as f:
        metadata = {"name": local_path.name, "parents": [folder_id]}
        media    = MediaIoBaseUpload(f, mimetype="image/jpeg", resumable=True)
        file     = drive_service.files().create(
            body=metadata,
            media_body=media,
            fields="id, name",
        ).execute()
    return file["id"]


# =============================================================================
# Download phase — fetch everything to local disk before any AI processing
# =============================================================================

def download_user_image(
    drive_service,
    filename: str,
    unprocessed_folder_files: dict[str, str],
) -> Path | None:
    """
    Download the user's submitted image from the unprocessed Drive folder.
    Saves to: downloads/unprocessed/<filename>.jpg
    Returns local Path or None if the file wasn't found in Drive.
    """
    file_id = unprocessed_folder_files.get(filename)
    if not file_id:
        print(f"  ❌  '{filename}' not found in unprocessed folder.")
        print(f"       Available: {list(unprocessed_folder_files.keys())}")
        return None

    local_path = DIR_UNPROCESSED / filename
    return download_to_local(drive_service, file_id, local_path)


def download_style_references(
    drive_service,
    style_name: str,
    style_dict: dict,
    max_refs: int = 3,
) -> list[Path]:
    """
    Download up to max_refs reference images for a style.
    Saves to: downloads/styles/<style-name>/<filename>.jpg
    Already-cached files are skipped (no re-download).
    Returns list of local Paths.
    """
    folder_id     = style_dict["folder_id"]
    picture_names = style_dict["pictures"][:max_refs]

    # Sanitise style name for use as a directory name
    safe_name = re.sub(r'[^\w\s-]', '', style_name).strip().replace(' ', '-')
    style_dir = DIR_STYLES / safe_name
    style_dir.mkdir(parents=True, exist_ok=True)

    # Determine which files aren't cached yet
    needed = [
        n for n in picture_names
        if not (style_dir / Path(n).stem).with_suffix(".jpg").exists()
    ]

    # Only hit Drive API if there's something missing
    folder_files: dict[str, str] = {}
    if needed:
        print(f"    📂  Fetching Drive file list for '{style_name}' ({len(needed)} missing) ...")
        folder_files = list_files_in_folder2(drive_service, folder_id)

    local_refs: list[Path] = []
    for name in picture_names:
        local_path = style_dir / name

        cached = local_path.with_suffix(".jpg")
        if cached.exists():
            print(f"    ✔  Cached ref: {cached}")
            local_refs.append(cached)
            continue

        file_id = folder_files.get(name)
        if not file_id:
            print(f"    ⚠️  '{name}' not found in style Drive folder — skipping")
            continue

        try:
            saved = download_to_local(drive_service, file_id, local_path)
            local_refs.append(saved)
        except Exception as e:
            print(f"    ⚠️  Could not download '{name}': {e}")

    return local_refs

def process_rows(drive_service, sheets_service, gemini_client):
    unprocessed_rows = get_unprocessed_rows(sheets_service)
    # jobs = build_pending_jobs(unprocessed_rows, google_drive_files)
    records = parse_rows(unprocessed_rows)

    for idx, record in enumerate(records, 1):

        print(f"[{idx}/{len(records)}] Processing row {record['row_index']} ...")
        name      = record["name"]
        email     = record["email"]
        filename  = record["file"]
        style_raw = record["style_raw"]

        # assets = prepare_job_assets(
        #     drive_service=drive_service,
        #     job=job,
        #     unprocessed_folder_id=FOLDER_ID_FOR_UNPROCESSED,
        # )

        # if not assets["ref_image_bytes"]:
        #     print(f"⚠️ No reference images found for style '{job['matched_style_key']}'")
        #     continue

        # prompt = (
        #     f"Use the reference images to restyle the source image in the '{job['matched_style_key']}' look. "
        #     f"Keep the person realistic and preserve facial identity. Return only the edited image."
        # )

        # prompt = (
        # "Use the FIRST image as the identity-preserved source image. "
        # "The SECOND image and all additional images are hairstyle references only, not replacement subjects. "
        # "Transfer only the hairstyle from the reference images onto the person in the FIRST image. "
        # "Do not alter the person's face, identity, age, skin tone, facial features, expression, body, clothing, pose, background, or image composition. "
        # "Only change the hair so it becomes a detailed geometric all-back cornrow style with clean parts, symmetry, and precise braiding. "
        # "The edited result must clearly remain the same person from the FIRST image. "
        # "Return ONLY the edited image."
        # )        
        
        # new_image_bytes = generate_transformed_image(
        #     gemini_client=gemini_client,
        #     imagen_prompt=prompt,
        #     source_image_bytes=assets["source_image_bytes"],
        #     ref_image_bytes=assets["ref_image_bytes"],
        # )



        style_name, style_dict = match_style(style_raw)
        if not style_name:
            print(f"  ❌  Skipping — unknown style: '{style_raw}'")
            return False


        unprocessed_files = list_files_in_folder2(drive_service, FOLDER_ID_FOR_UNPROCESSED)


        source_path = download_user_image(drive_service, filename, unprocessed_files)
        if not source_path:
            return False

        # ── 3. Download style reference images to local disk ─────────────────────
        print(f"  ⬇️   Downloading reference images for '{style_name}' ...")
        ref_paths = download_style_references(drive_service, style_name, style_dict, max_refs=3)

        if not ref_paths:
            print(f"  ❌  No reference images available for '{style_name}' — skipping")
            return False

        print(f"  📎  {len(ref_paths)} reference(s) ready at:")
        for p in ref_paths:
            print(f"       {p}")

        person_description = describe_person(gemini_client, source_path)

        # ── Step 2: build prompt with injected description ────────────────────────
        prompt = build_transform_prompt(style_name, person_description)

        transformed_bytes = generate_transformed_image(
            gemini_client, prompt, source_path, ref_paths
        )

        # prompt = build_transform_prompt(style_name)
        # file_id = unprocessed_files.get(filename)

        # source_image_bytes = return_normalised_image(drive_service, file_id)


        # ref_images = get_style_reference_images(drive_service, style_dict, max_refs=1)



        # transformed_bytes = generate_transformed_image(
        #         gemini_client, prompt, source_image_bytes, ref_images)
        
        stem = filename.rsplit(".", 1)[0]
        output_filename = f"{filename}" # f"{stem}_{style_name.replace(' ', '_')}_transformed.jpg"

        if not transformed_bytes:
            print(f"  ❌  Generation failed for '{filename}'")
            continue

        # output_name = f"processed_{job['file'].rsplit('.', 1)[0]}.jpg"
        upload_bytes(
            service=drive_service,
            data=transformed_bytes,
            filename=output_filename,
            drive_folder_id=FOLDER_ID_TO_UPLOAD_PROCESSED,
            mime_type="image/jpeg",
        )


        # Mark row as processed only if row still matches
        if  transformed_bytes:
            update_status_by_identity(
                service=sheets_service,
                sheet_name='Sheet1',
                name=name,
                email=record["email"],
                file=record["file"],
                style=record["style_raw"],
                status_value="processed",)
            # mark_processed_if_row_matches(
            #     sheets_service=sheets_service,
            #     sheet_name='Sheet1',
            #     job=record,
            #     status_value="processed",
            # )
            print(f"✅ Uploaded processed image for row {record['row_index']}")
        # Here you can also mark sheet status = processed

# def build_transform_prompt(style_name: str) -> str:
#     """
#     Build an identity-preserving style transfer prompt.

#     Key principles that keep the person looking like themselves:
#       - Explicitly forbid changing the face, skin tone, body shape
#       - Frame it as clothing/outfit editing, NOT as regeneration
#       - Tell the model the person is already in the image and must stay
#     """
#     return (
#         # ── Who/what is in the images ─────────────────────────────────────
#         "Image 1 is a real photograph of a specific person. "
#         "Images 2 onwards are fashion reference photos showing the "
#         f"'{style_name}' style.\n\n"

#         # ── What to do ────────────────────────────────────────────────────
#         f"Edit Image 1 so the person is wearing an outfit inspired by the "
#         f"'{style_name}' style shown in the reference images. "
#         "Apply the clothing, fabric patterns, colours, accessories, and "
#         "overall aesthetic of the reference style to the person in Image 1.\n\n"

#         # ── Hard constraints — this is what stops it drifting ─────────────
#         "STRICT RULES — you must follow all of these:\n"
#         "1. DO NOT change the person's face, facial features, or skin tone in any way.\n"
#         "2. DO NOT change the person's body shape, height, or pose.\n"
#         "3. DO NOT replace the person with a different person or a generic model.\n"
#         "4. DO NOT add or remove people from the image.\n"
#         "5. ONLY change the clothing, outfit, and accessories.\n"
#         "6. Keep the background and lighting the same as in Image 1.\n"
#         "7. The output must look like a photo of the SAME person from Image 1 "
#         "wearing different clothes — not a new person, not an illustration.\n\n"

#         "Output only the final edited image."
#     )


# def build_transform_prompt(style_name: str) -> str:
#     """
#     Identity-preserving hairstyle transfer prompt.

#     Key principles:
#       - Image 1 is the subject (person to edit)
#       - Image 2+ are hairstyle references for the given style
#       - ONLY the hairstyle changes — face, skin, body, clothes, background stay identical
#     """
#     return (
#         # ── Image roles ───────────────────────────────────────────────────
#         "The FIRST image is a real photograph of a specific person. "
#         f"The SECOND image (and any further images) shows the hairstyle for the '\'{style_name}\'' style: "
#         "a detailed, precise reference of the exact hairstyle to apply — "
#         "including the braid pattern, parting, geometry, symmetry, and technique.\n\n"

#         # ── What to do ────────────────────────────────────────────────────
#         "Make the FIRST image look like the person has the same hairstyle shown in the SECOND image. "
#         "Replicate the braid pattern, parting structure, geometric layout, symmetry, "
#         "and overall hairstyle aesthetic from the reference onto the person in the FIRST image. Also make sure the generated image looks natural and photorealistic.\n\n"

#         # ── Hard constraints ──────────────────────────────────────────────
#         "STRICT RULES — you must follow ALL of these:\n"
#         "1. ONLY change the hairstyle. Nothing else.\n"
#         "2. DO NOT change the person's face, facial features, skin tone, or expression.\n"
#         "3. DO NOT change the person's clothing, outfit, or accessories.\n"
#         "4. DO NOT change the person's body shape, height, or pose.\n"
#         "5. DO NOT change the background or lighting.\n"
#         "6. DO NOT replace the person with a different person or a generic model.\n"
#         "7. The result must look like a photo of the SAME person from the FIRST image "
#         "with a different hairstyle — not a new person, not an illustration.\n\n"

#         "Return ONLY the generated image."
#     )


def describe_person(gemini_client: genai.Client, source_image_path: Path) -> str:
    """
    Step 1 of 2: Use Gemini Vision to precisely describe the person's fixed
    features — glasses, skin tone, face, clothing — so we can lock them down
    in the generation prompt and prevent the model from drifting.
    """
    print("  🔍  Analysing source image features ...")
    response = gemini_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_bytes(data=load_image_bytes(source_image_path), mime_type="image/jpeg"),
            (
                "Describe the following features of the person in this photo with high precision. "
                "Be specific about colours, shapes, and details:\n"
                "1. Glasses: frame shape, frame colour, lens colour/tint, any distinctive markings\n"
                "2. Skin tone: describe precisely (e.g. deep brown, warm medium brown, etc.)\n"
                "3. Clothing: garment type, colour, neckline\n"
                "4. Background: colour, texture, any objects\n"
                "5. Lighting: direction and quality\n"
                "Return a concise bullet list. No introduction, no conclusion."
            ),
        ],
    )
    description = response.text.strip()
    print(f"  📋  Features: {description[:120]}...")
    return description


def build_transform_prompt(style_name: str, person_description: str) -> str:
    """
    Step 2 of 2: Build the generation prompt injecting the person's exact
    features as hard anchors so the model cannot drift from the original.

    Strategy:
      - Inject Vision-extracted feature description to lock face/glasses/skin
      - "Surgical edit" framing keeps scope to hair only
      - Explicit baby-hair / hairline blending rules target the main failure mode
      - Photorealism demanded three times in different ways
    """
    return (
        # ── Lock identity with Vision-extracted features ───────────────────
        "You are making a SURGICAL EDIT to a real photograph. "
        "The FIRST image is the source. "
        "The person in the FIRST image has these EXACT features that must be "
        "preserved pixel-perfectly in the output:\n"
        f"{person_description}\n\n"

        # ── Define the ONLY permitted change ──────────────────────────────
        "The ONE AND ONLY change you are allowed to make is: replace the hairstyle.\n\n"

        # ── Reference description ─────────────────────────────────────────
        f"The SECOND image shows the target hairstyle '{style_name}'. "
        "Study the braid pattern, parting lines, sectioning geometry, "
        "braid thickness, and symmetry exactly as shown.\n\n"

        # ── Instruction ───────────────────────────────────────────────────
        "Apply that hairstyle to the person in the FIRST image so the result "
        "looks like a real photograph taken of the same person wearing the new hairstyle. "
        "The hair texture and braids must look like real physical hair — "
        "NOT drawn, NOT illustrated, NOT CGI.\n\n"

        # ── Hairline blending (main failure point) ────────────────────────
        "Critical hairline rules:\n"
        "- NO drawn or illustrated baby hairs along the hairline — any edge hairs "
        "must look like real, soft, natural flyaways from a photograph.\n"
        "- Blend the hairline into the forehead with zero visible seam or border.\n"
        "- Scalp skin between braids must exactly match the skin tone listed above.\n"
        "- Hair near the ears and temples must sit naturally, not float.\n\n"

        # ── Hard constraints ───────────────────────────────────────────────
        "STRICT RULES — each violation makes the output unusable:\n"
        "1. ONLY change the hair. Zero other changes permitted.\n"
        "2. Glasses: preserve the EXACT frame shape, colour, and position listed above.\n"
        "3. Face: preserve the exact skin tone, features, expression, and eye colour.\n"
        "4. Body: preserve clothing, pose, and body shape exactly.\n"
        "5. Background and lighting must remain identical.\n"
        "6. Output must look like a real photograph — not art, not illustration.\n\n"

        "Return ONLY the edited image."
    )


def mark_processed_if_row_matches(
    sheets_service,
    sheet_name: str,
    job: dict,
    status_value: str = "processed",
    spreadsheet_id='1chGGVMDcoL_9OO69rsqemXlvN389oyCKQG74wq-QB5o',
):
    """
    Update the status cell only if the row still matches the original
    name/email/file/style values.
    """
    rows = read_all(sheets_service, spreadsheet_id, sheet_name)
    if not rows:
        raise ValueError("Sheet is empty.")

    header = rows[0]
    required = ["name", "email", "file", "style", "status"]
    for col in required:
        if col not in header:
            raise ValueError(f"Missing required column '{col}'")

    row_number = job["row_index"]
    row_index = row_number - 1  # convert sheet row number -> list index

    if row_index >= len(rows):
        raise ValueError(f"Row {row_number} no longer exists in sheet.")

    row = rows[row_index]

    def get_val(col_name: str):
        idx = header.index(col_name)
        return row[idx] if idx < len(row) else None

    # Verify the row still matches before updating
    if (
        get_val("name") != job["name"] or
        get_val("email") != job["email"] or
        get_val("file") != job["file"] or
        get_val("style") != job["style_raw"]
    ):
        raise ValueError(
            f"Row {row_number} changed; refusing to update status. "
            f"Expected name/email/file/style for {job['file']}"
        )

    status_col_index = header.index("status") + 1  # 1-based
    status_col_letter = col_to_letter(status_col_index)
    cell = f"{sheet_name}!{status_col_letter}{row_number}"

    update_cell(sheets_service, spreadsheet_id, cell, status_value)
    print(f"✅ Marked row {row_number} as {status_value}")


def get_style_reference_images(
    drive_service,
    style_dict: dict,
    max_refs: int = 3,
) -> list[bytes]:
    """
    Fetch up to `max_refs` reference pictures from the style's Drive folder.
    Returns a list of normalised JPEG bytes.
    """
    folder_id      = style_dict["folder_id"]
    picture_names  = style_dict["pictures"][:max_refs]   # limit to avoid large payloads

    # Build a name→id map of what's actually in the folder
    folder_files = list_files_in_folder2(drive_service, folder_id)

    ref_images = []
    for name in picture_names:
        file_id = folder_files.get(name)
        if not file_id:
            print(f"    Reference image '{name}' not found in style folder — skipping")
            continue
        try:
            img_bytes = return_normalised_image(drive_service, file_id)
            ref_images.append(img_bytes)
            print(f"    📎 Loaded reference: {name}")
        except Exception as e:
            print(f"    Could not load reference '{name}': {e}")

    return ref_images



def main():

    print("Authenticating with Google Sheets...")
    sheet_service = get_sheets_service()
    drive_service = get_drive_service()
    print("✅ Authenticated!\n")

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise SystemExit("Missing GEMINI_API_KEY (or GOOGLE_API_KEY) env var.")

    client = genai.Client(api_key=api_key)

    process_rows(drive_service, sheet_service, client)

    # FOLDER_ID_FOR_UNPROCESSED = "14Sat-oN1mqbZq8o_A1mwXTiJ02iEeJT8"   # From URL: /drive/folders/<THIS_PART>
    # # ─────────────────────────────────────────────────────────────────────────

    # print("Authenticating with Google Drive...")
    # service = get_drive_service()
    # print("✅ Authenticated!\n")

    # # 1. List files
    # print(f"📂 Files in folder {FOLDER_ID}:")
    # files = list_files_in_folder(service, FOLDER_ID)
    # if not files:
    #     print("  (folder is empty)")
    # for f in files:
    #     size = f.get("size", "—")
    #     print(f"  [{f['id']}]  {f['name']}  ({f['mimeType']}, {size} bytes)")
    # print()



if __name__ == "__main__":
    main()