import base64
import hashlib
import json
import logging
import os

import httpx, random, string

from datetime import date, timedelta
from httpx import Response

from pilucca.conf import settings

logger = logging.getLogger(__name__)


def create_intervals(start: date, end: date):
    date_intervals = []

    # Calculate days until next Monday (Monday is 0 in weekday())
    # If today is Monday, days_ahead will be 0
    days_ahead = (0 - start.weekday()) % 7

    # If it's already past Monday (e.g., Saturday), move to next week's Monday
    # Note: If start is Monday, this stays on start.
    # If you want it to ALWAYS be 'next' Monday even on a Monday, use:
    # days_ahead = 7 - start.weekday() if start.weekday() >= 0 else ...

    current_start = start + timedelta(days=days_ahead)

    # Loop while the current start date is within the requested range
    while current_start <= end:
        # Define the end of the week (Sunday)
        current_end = current_start + timedelta(days=6)

        # Optional: Cap the interval at the 'end' date if you don't want to overshoot
        # actual_end = min(current_end, end)

        date_intervals.append([current_start, current_end])

        # Move to the start of the next week
        current_start = current_end + timedelta(days=1)

    return date_intervals


def group_absence_dates(dates_list):
    if not dates_list:
        return []

    # 1. Sort and remove duplicates to ensure logic works
    sorted_dates = sorted(set(dates_list))

    ranges = []
    start_date = sorted_dates[0]
    end_date = sorted_dates[0]

    # 2. Iterate starting from the second element
    for current_date in sorted_dates[1:]:
        # If current day is consecutive (previous day + 1)
        if current_date == end_date + timedelta(days=1):
            end_date = current_date
        else:
            # Gap found: Close the previous range
            ranges.append((start_date, end_date))
            # Start a new range
            start_date = current_date
            end_date = current_date

    # 3. Don't forget to append the final range after the loop finishes
    ranges.append((start_date, end_date))

    # 4. Format the output: "without end" if it's a single day
    formatted_result = []
    for s, e in ranges:
        entry = {'start': s, 'end': e if s != e else None}
        # if s != e:
        #     entry['end'] = e
        formatted_result.append(entry)

    return formatted_result


def hash_sha256(code_verifier: str):
    # 1. Hash it using standard SHA-256 (No HMAC/Secret Key)
    hash_object = hashlib.sha256(code_verifier.encode('ascii'))
    binary_digest = hash_object.digest()

    # 2. Base64URL encode and strip the padding (=)
    code_challenge = base64.urlsafe_b64encode(binary_digest).decode('ascii').rstrip('=')

    return code_challenge

def hook_response(response: Response) :
    request = response.request
    response.read()

    # Response cookies are in a dedicated jar
    res_cookies = dict(response.cookies)

    log_msg = (
        f"\n{'=' * 60}\n"
        f"HTTP {request.method} REQUEST\n"
        f"URL: {request.url}\n"
        f"Headers: {json.dumps(dict(request.headers), indent=4)}\n"
        f"{'-' * 60}\n"
        f"HTTP {response.status_code} {response.reason_phrase}\n"
        f"Headers: {json.dumps(dict(response.headers), indent=4)}\n"
        f"Cookies (Received): {res_cookies if res_cookies else 'None'}\n"
        f"Body: {response.text[:500]}{'...' if len(response.text) > 500 else ''}\n"
        f"{'=' * 60}"
    )

    logger.info(log_msg)

def send_telegram_notification(message: str, mode:str = 'HTML'):
    token = settings.TELEGRAM_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }

    event_hooks = {
        "request": [],
        "response": [],
    }

    if settings.DEBUG:
        event_hooks["response"] = [hook_response]

    with httpx.Client(event_hooks=event_hooks) as client:
        response = client.post(url, data=payload)
        return response.json()