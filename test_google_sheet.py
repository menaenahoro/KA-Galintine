#!/usr/bin/env python3
"""
Sample: Google Sheets Access
==============================
Demonstrates how to authenticate with Google Sheets and:
  - Read all data from a sheet
  - Read a specific range
  - Write / append rows
  - Update a single cell
  - Clear a range

Requirements:
    pip install google-auth google-auth-oauthlib google-api-python-client

Setup:
    1. Go to https://console.cloud.google.com
    2. Enable "Google Sheets API"  (and Drive API if you need to list sheets)
    3. Create OAuth 2.0 Desktop credentials → Download as credentials.json
    4. Run this script — browser will open for login on first run

How to find your Spreadsheet ID:
    Open the sheet in your browser. The URL looks like:
    https://docs.google.com/spreadsheets/d/1ABC...XYZ/edit
    The long string between /d/ and /edit is the spreadsheet ID.
"""
import os
import json
import sys
import tempfile

from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

# ── Scopes ────────────────────────────────────────────────────────────────────
# spreadsheets.readonly  → read only (safer for testing)
# spreadsheets           → full read/write
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


# ─────────────────────────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────────────────────────
def _require_env(name: str) -> str:
    """Read a required environment variable or exit with a helpful message."""
    value = os.getenv(name)
    if not value:
        print(f"\n❌  Environment variable '{name}' is not set!")
        if name == "GOOGLE_CREDENTIALS_JSON":
            print("    Download your OAuth credentials JSON from Google Cloud Console")
            print("    and set: export GOOGLE_CREDENTIALS_JSON='<paste file contents>'")
        elif name == "GOOGLE_TOKEN_JSON":
            print("    Run the script once without GOOGLE_TOKEN_JSON set.")
            print("    A browser will open for login, then the token will be printed.")
            print("    Copy that output and set: export GOOGLE_TOKEN_JSON='<paste token>'")
        sys.exit(1)
    return value

# def get_sheets_service():
#     """
#     Authenticate and return a Sheets API service client.
#     - First run: opens browser for Google login, saves token.json
#     - Later runs: reuses token.json silently
#     """
#     creds = None

#     if Path("token.json").exists():
#         creds = Credentials.from_authorized_user_file("token.json", SCOPES)

#     if not creds or not creds.valid:
#         if creds and creds.expired and creds.refresh_token:
#             creds.refresh(Request())
#         else:
#             flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
#             creds = flow.run_local_server(port=0)
#         with open("token.json", "w") as f:
#             f.write(creds.to_json())

#     return build("sheets", "v4", credentials=creds)

def get_sheets_service():
    """
    Authenticate using ENV vars and return a Sheets API service client.

    GOOGLE_CREDENTIALS_JSON  — contents of your OAuth credentials JSON
    GOOGLE_TOKEN_JSON        — contents of token JSON (generated after first login)

    On first run (no GOOGLE_TOKEN_JSON set):
      - Browser opens for Google login
      - Token JSON is printed to stdout — save it as GOOGLE_TOKEN_JSON

    On subsequent runs:
      - Token is read from GOOGLE_TOKEN_JSON silently
      - Refreshed automatically if expired
    """
    creds = None
    token_json = os.getenv("GOOGLE_TOKEN_JSON")

    # ── Load existing token from ENV ──────────────────────────────────────────
    if token_json:
        try:
            creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
        except Exception as e:
            print(f"⚠️  Could not load GOOGLE_TOKEN_JSON: {e}. Re-authenticating...")
            creds = None

    # ── Refresh or do first-time login ────────────────────────────────────────
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Write credentials JSON to a temp file (InstalledAppFlow needs a file path)
            creds_data = _require_env("GOOGLE_CREDENTIALS_JSON")
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
                tmp.write(creds_data)
                tmp_path = tmp.name
            try:
                flow = InstalledAppFlow.from_client_secrets_file(tmp_path, SCOPES)
                creds = flow.run_local_server(port=0)
            finally:
                os.unlink(tmp_path)

        # ── Print new token so user can save it as GOOGLE_TOKEN_JSON ──────────
        token_str = creds.to_json()
        print("\n" + "=" * 60)
        print("✅  Auth successful! Save this as your GOOGLE_TOKEN_JSON env var:")
        print("=" * 60)
        print(token_str)
        print("=" * 60 + "\n")

    return build("sheets", "v4", credentials=creds)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def read_all(service, spreadsheet_id: str, sheet_name: str = "Sheet1") -> list[list]:
    """Read all rows from a sheet tab."""
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=sheet_name,          # no range = entire sheet
    ).execute()
    return result.get("values", [])


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


# ─────────────────────────────────────────────────────────────────────────────
# Run demo
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    # ── CHANGE THIS ───────────────────────────────────────────────────────────
    SPREADSHEET_ID = "1chGGVMDcoL_9OO69rsqemXlvN389oyCKQG74wq-QB5o"   # From URL: /spreadsheets/d/<THIS_PART>/edit
    # ─────────────────────────────────────────────────────────────────────────

    print("Authenticating with Google Sheets...")
    service = get_sheets_service()
    print("✅ Authenticated!\n")

    # 1. List all sheet tabs
    print("📋 Sheet tabs in this spreadsheet:")
    tabs = get_sheet_names(service, SPREADSHEET_ID)
    for tab in tabs:
        print(f"   - {tab}")
    print()

    # Use the first tab for all examples below
    tab = tabs[0] if tabs else "Sheet1"

    # 2. Read all data
    print(f"📖 All data in '{tab}':")
    rows = read_all(service, SPREADSHEET_ID, tab)
    if not rows:
        print("  (sheet is empty)")
    for i, row in enumerate(rows):
        print(f"  Row {i+1}: {row}")
    print()

    # # 3. Read a specific range
    # cell_range = f"{tab}!A1:C5"
    # print(f"🔍 Reading range '{cell_range}':")
    # partial = read_range(service, SPREADSHEET_ID, cell_range)
    # for row in partial:
    #     print(f"  {row}")
    # print()

    # # 4. Write some data
    # print(f"✏️  Writing sample data to '{tab}!A1'...")
    # write_rows(service, SPREADSHEET_ID, f"{tab}!A1", [
    #     ["Name",    "Score", "Status"],
    #     ["Alice",   95,      "Pass"],
    #     ["Bob",     72,      "Pass"],
    #     ["Charlie", 45,      "Fail"],
    # ])
    # print()

    # # 5. Append a new row
    # print(f"➕ Appending a new row to '{tab}'...")
    # append_rows(service, SPREADSHEET_ID, tab, [
    #     ["Diana", 88, "Pass"]
    # ])
    # print()

    # # 6. Update a single cell
    # print(f"🎯 Updating cell {tab}!C3 ...")
    # update_cell(service, SPREADSHEET_ID, f"{tab}!C3", "Distinction")
    # print()

    # # 7. Read back to confirm
    # print(f"📖 Final state of '{tab}!A1:C5':")
    # final = read_range(service, SPREADSHEET_ID, f"{tab}!A1:C5")
    # for row in final:
    #     print(f"  {row}")
    # print()

    print("✅ Google Sheets sample complete!")