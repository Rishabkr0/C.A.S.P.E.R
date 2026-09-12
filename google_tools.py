import os
import datetime
import logging
from typing import Optional, List
from livekit.agents import function_tool, RunContext

logger = logging.getLogger("google-tools")

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    logger.warning("Google API client libraries not installed.")

# If modifying these scopes, delete the file token.json.
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.readonly'
]

CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'

def _get_google_credentials():
    """Handles the OAuth2 flow and returns valid credentials."""
    if not GOOGLE_AVAILABLE:
        raise RuntimeError("Google libraries not installed.")
        
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(f"Missing {CREDENTIALS_FILE}. Please download it from Google Cloud Console.")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Save the credentials for the next run
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
            
    return creds


# ==========================================
# GOOGLE CALENDAR TOOLS
# ==========================================

@function_tool()
async def google_calendar_get_events(context: RunContext, max_results: int = 10) -> str:
    """
    Get upcoming events from the user's primary Google Calendar.
    
    Args:
        max_results: Maximum number of events to fetch.
    """
    try:
        creds = _get_google_credentials()
        service = build('calendar', 'v3', credentials=creds)

        # Call the Calendar API
        now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        events_result = service.events().list(
            calendarId='primary', timeMin=now,
            maxResults=max_results, singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])

        if not events:
            return 'No upcoming events found.'
            
        result = ["Upcoming events:"]
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            summary = event.get('summary', 'No Title')
            result.append(f"- {start}: {summary}")
            
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Google Calendar error: {e}")
        return f"Failed to fetch calendar events: {str(e)}"


@function_tool()
async def google_calendar_add_event(context: RunContext, summary: str, start_time_iso: str, end_time_iso: str) -> str:
    """
    Add a new event to the user's primary Google Calendar.
    
    Args:
        summary: Title of the event.
        start_time_iso: Start time in ISO format (e.g. 2026-10-25T10:00:00-07:00).
        end_time_iso: End time in ISO format.
    """
    try:
        creds = _get_google_credentials()
        service = build('calendar', 'v3', credentials=creds)

        event = {
            'summary': summary,
            'start': {
                'dateTime': start_time_iso,
                'timeZone': 'UTC',  # Assuming UTC if offset not provided, API handles offsets
            },
            'end': {
                'dateTime': end_time_iso,
                'timeZone': 'UTC',
            },
        }

        event_result = service.events().insert(calendarId='primary', body=event).execute()
        return f"Event created: {event_result.get('htmlLink')}"
        
    except Exception as e:
        logger.error(f"Google Calendar error: {e}")
        return f"Failed to create event: {str(e)}"


# ==========================================
# GOOGLE SHEETS TOOLS
# ==========================================

@function_tool()
async def google_sheets_read(context: RunContext, spreadsheet_id: str, range_name: str) -> str:
    """
    Read data from a Google Sheet.
    
    Args:
        spreadsheet_id: The ID of the spreadsheet (found in its URL).
        range_name: The A1 notation of the range to read (e.g. 'Sheet1!A1:E').
    """
    try:
        creds = _get_google_credentials()
        service = build('sheets', 'v4', credentials=creds)

        # Call the Sheets API
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
        values = result.get('values', [])

        if not values:
            return 'No data found in the specified range.'
            
        formatted_rows = []
        for row in values:
            formatted_rows.append(" | ".join([str(cell) for cell in row]))
            
        return "Sheet Data:\n" + "\n".join(formatted_rows)
        
    except Exception as e:
        logger.error(f"Google Sheets error: {e}")
        return f"Failed to read sheet: {str(e)}"


@function_tool()
async def google_sheets_append(context: RunContext, spreadsheet_id: str, range_name: str, values_csv: str) -> str:
    """
    Append rows of data to a Google Sheet.
    
    Args:
        spreadsheet_id: The ID of the spreadsheet.
        range_name: The sheet name or range to append to.
        values_csv: Multiline string of comma-separated values to append.
    """
    try:
        creds = _get_google_credentials()
        service = build('sheets', 'v4', credentials=creds)

        # Parse CSV string into 2D list
        values = []
        for row in values_csv.strip().split('\n'):
            values.append([val.strip() for val in row.split(',')])

        body = {
            'values': values
        }
        
        result = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id, 
            range=range_name,
            valueInputOption='USER_ENTERED', 
            body=body
        ).execute()
        
        updated_rows = result.get('updates', {}).get('updatedRows', 0)
        return f"Successfully appended {updated_rows} rows to the sheet."
        
    except Exception as e:
        logger.error(f"Google Sheets error: {e}")
        return f"Failed to append to sheet: {str(e)}"


# Export tools
GOOGLE_TOOLS = [
    google_calendar_get_events,
    google_calendar_add_event,
    google_sheets_read,
    google_sheets_append
]
