# #!/usr/bin/env python3
# """
# Sample: Google Drive Access
# ============================
# Demonstrates how to authenticate with Google Drive and:
#   - List files in a folder
#   - Download a file
#   - Upload a file

# Requirements:
#     pip install google-auth google-auth-oauthlib google-api-python-client

# Setup:
#     1. Go to https://console.cloud.google.com
#     2. Enable "Google Drive API"
#     3. Create OAuth 2.0 Desktop credentials → Download as credentials.json
#     4. Run this script — browser will open for login on first run
# """

# import io
# import os
# import json
# import sys
# import tempfile
# from pathlib import Path
# from google.auth.transport.requests import Request
# from google.oauth2.credentials import Credentials
# from google_auth_oauthlib.flow import InstalledAppFlow
# from googleapiclient.discovery import build
# from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
# from dotenv import load_dotenv

# load_dotenv()

# # ── Scopes ────────────────────────────────────────────────────────────────────
# # drive.readonly  → read only (safer for testing)
# # drive           → full read/write (needed for upload)
# SCOPES = ["https://www.googleapis.com/auth/drive"]


# # ─────────────────────────────────────────────────────────────────────────────
# # Auth
# # ─────────────────────────────────────────────────────────────────────────────


# # def _require_env(name: str) -> str:
# #     """Read a required environment variable or exit with a helpful message."""
# #     value = os.getenv(name)
# #     if not value:
# #         # print(f"\n❌  Environment variable '{name}' is not set!")
# #         if name == "GOOGLE_CREDENTIALS_JSON":
# #             # print("    Download your OAuth credentials JSON from Google Cloud Console")
# #             # print("    and set: export GOOGLE_CREDENTIALS_JSON='<paste file contents>'")
# #         elif name == "GOOGLE_TOKEN_JSON":
# #             print("    Run the script once without GOOGLE_TOKEN_JSON set.")
# #             print("    A browser will open for login, then the token will be printed.")
# #             print("    Copy that output and set: export GOOGLE_TOKEN_JSON='<paste token>'")
# #         sys.exit(1)
# #     return value


# def get_drive_service():
#     """
#     Authenticate using ENV vars and return a Drive API service client.

#     GOOGLE_CREDENTIALS_JSON  — contents of your OAuth credentials JSON
#     GOOGLE_TOKEN_JSON        — contents of token JSON (generated after first login)

#     On first run (no GOOGLE_TOKEN_JSON set):
#       - Browser opens for Google login
#       - Token JSON is printed to stdout — save it as GOOGLE_TOKEN_JSON

#     On subsequent runs:
#       - Token is read from GOOGLE_TOKEN_JSON silently
#       - Refreshed automatically if expired
#     """
#     creds = None
#     token_json = os.getenv("GOOGLE_TOKEN_JSON")

#     # ── Load existing token from ENV ──────────────────────────────────────────
#     if token_json:
#         try:
#             creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
#         except Exception as e:
#             print(f"⚠️  Could not load GOOGLE_TOKEN_JSON: {e}. Re-authenticating...")
#             creds = None

#     # ── Refresh or do first-time login ────────────────────────────────────────
#     if not creds or not creds.valid:
#         if creds and creds.expired and creds.refresh_token:
#             creds.refresh(Request())
#         else:
#             # Write credentials JSON to a temp file (InstalledAppFlow needs a file path)
#             creds_data = _require_env("GOOGLE_CREDENTIALS_JSON")
#             with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
#                 tmp.write(creds_data)
#                 tmp_path = tmp.name
#             try:
#                 flow = InstalledAppFlow.from_client_secrets_file(tmp_path, SCOPES)
#                 creds = flow.run_local_server(port=0)
#             finally:
#                 os.unlink(tmp_path)

#         # ── Print new token so user can save it as GOOGLE_TOKEN_JSON ──────────
#         token_str = creds.to_json()
#         print("\n" + "=" * 60)
#         print("✅  Auth successful! Save this as your GOOGLE_TOKEN_JSON env var:")
#         print("=" * 60)
#         print(token_str)
#         print("=" * 60 + "\n")

#     return build("drive", "v3", credentials=creds)

# # ─────────────────────────────────────────────────────────────────────────────
# # Examples
# # ─────────────────────────────────────────────────────────────────────────────

# def list_files_in_folder(service, folder_id: str) -> list[dict]:
#     """List all files inside a Drive folder."""
#     query = f"'{folder_id}' in parents and trashed = false"
#     results = []
#     page_token = None

#     while True:
#         resp = service.files().list(
#             q=query,
#             fields="nextPageToken, files(id, name, mimeType, size)",
#             pageToken=page_token,
#         ).execute()

#         results.extend(resp.get("files", []))
#         page_token = resp.get("nextPageToken")
#         if not page_token:
#             break

#     return results


# def download_file(service, file_id: str, save_path: str):
#     """Download a file from Drive by its file ID."""
#     request = service.files().get_media(fileId=file_id)
#     buf = io.BytesIO()
#     downloader = MediaIoBaseDownload(buf, request)

#     done = False
#     while not done:
#         status, done = downloader.next_chunk()
#         print(f"  Download progress: {int(status.progress() * 100)}%")

#     with open(save_path, "wb") as f:
#         f.write(buf.getvalue())
#     print(f"  Saved to: {save_path}")


# def upload_file(service, local_path: str, drive_folder_id: str, mime_type: str = "application/octet-stream") -> str:
#     """Upload a local file to a Drive folder. Returns the new file's Drive ID."""
#     filename = Path(local_path).name
#     metadata = {"name": filename, "parents": [drive_folder_id]}

#     with open(local_path, "rb") as f:
#         media = MediaIoBaseUpload(f, mimetype=mime_type, resumable=True)
#         file = service.files().create(
#             body=metadata,
#             media_body=media,
#             fields="id, name"
#         ).execute()

#     print(f"  Uploaded '{filename}' → Drive ID: {file['id']}")
#     return file["id"]


# def upload_bytes(service, data: bytes, filename: str, drive_folder_id: str, mime_type: str = "image/jpeg") -> str:
#     """Upload raw bytes to Drive (useful when you don't have a local file)."""
#     metadata = {"name": filename, "parents": [drive_folder_id]}
#     media = MediaIoBaseUpload(io.BytesIO(data), mimetype=mime_type, resumable=True)
#     file = service.files().create(
#         body=metadata,
#         media_body=media,
#         fields="id, name"
#     ).execute()
#     print(f"  Uploaded '{filename}' → Drive ID: {file['id']}")
#     return file["id"]


# def delete_file(service, file_id: str):
#     """Move a file to trash."""
#     service.files().delete(fileId=file_id).execute()
#     print(f"  Deleted file ID: {file_id}")


# # ─────────────────────────────────────────────────────────────────────────────
# # Run demo
# # ─────────────────────────────────────────────────────────────────────────────

# if __name__ == "__main__":

#     # ── CHANGE THESE ──────────────────────────────────────────────────────────
#     FOLDER_ID = "14Sat-oN1mqbZq8o_A1mwXTiJ02iEeJT8"   # From URL: /drive/folders/<THIS_PART>
#     # ─────────────────────────────────────────────────────────────────────────

#     print("Authenticating with Google Drive...")
#     service = get_drive_service()
#     print("✅ Authenticated!\n")

#     # 1. List files
#     print(f"📂 Files in folder {FOLDER_ID}:")
#     files = list_files_in_folder(service, FOLDER_ID)
#     if not files:
#         print("  (folder is empty)")
#     for f in files:
#         size = f.get("size", "—")
#         print(f"  [{f['id']}]  {f['name']}  ({f['mimeType']}, {size} bytes)")
#     print()

#     # # 2. Download first file (if any)
#     # if files:
#     #     first = files[0]
#     #     print(f"⬇️  Downloading '{first['name']}' ...")
#     #     download_file(service, first["id"], f"downloaded_{first['name']}")
#     #     print()

#     # # 3. Upload a test file
#     # test_file = "test_upload.txt"
#     # with open(test_file, "w") as f:
#     #     f.write("Hello from Google Drive API sample!")

#     # print(f"⬆️  Uploading '{test_file}' ...")
#     # new_id = upload_file(service, test_file, FOLDER_ID, mime_type="text/plain")
#     # os.remove(test_file)
#     # print()

#     # # 4. Clean up — delete the test file we just uploaded
#     # print(f"🗑️  Deleting test upload (ID: {new_id}) ...")
#     # delete_file(service, new_id)
#     # print()

#     print("✅ Google Drive sample complete!")