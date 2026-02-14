import datetime
import httpx
from urllib.parse import parse_qsl

def get_har_post_data(request):
    # Ensure the request has been read into memory
    try:
        content = request.content
    except httpx.RequestNotRead:
        return None # Or handle accordingly

    if not content:
        return None

    return {
        "mimeType": request.headers.get("content-type", "application/octet-stream"),
        "text": content.decode("utf-8", errors="replace")
    }


def create_har_entry_old(response: httpx.Response):
    request: httpx.Request = response.request
    request.read()
    response.read()
    """Formats an httpx exchange into a HAR-compatible dictionary."""
    return {
        "startedDateTime": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "time": response.elapsed.total_seconds() * 1000,
        "request": {
            "method": request.method,
            "url": str(request.url),
            "httpVersion": "HTTP/1.1",
            "headers": [{"name": k, "value": v} for k, v in request.headers.items()],
            "queryString": [],
            "cookies": [],
            "headersSize": -1,
            "bodySize": len(request.content),
            "postData": get_har_post_data(request),
        },
        "response": {
            "status": response.status_code,
            "statusText": response.reason_phrase,
            "httpVersion": "HTTP/1.1",
            "headers": [{"name": k, "value": v} for k, v in response.headers.items()],
            "cookies": [],
            "content": {
                "size": len(response.content),
                "mimeType": response.headers.get("content-type", "application/octet-stream"),
                "text": response.text,
            },
            "redirectURL": "",
            "headersSize": -1,
            "bodySize": len(response.content),
        },
        "cache": {},
        "timings": {"send": 0, "wait": 0, "receive": 0}
    }

def create_har_entry(response: httpx.Response):
    # Ensure request and response bodies are read to avoid RuntimeErrors
    request = response.request
    request.read()
    response.read()

    # 1. Parse Cookies from Request
    # Note: request.headers.get("cookie") is a raw string, we parse it for the list format
    req_cookies = []
    cookie_header = request.headers.get("cookie", "")
    if cookie_header:
        for part in cookie_header.split(";"):
            if "=" in part:
                name, value = part.strip().split("=", 1)
                req_cookies.append({"name": name, "value": value, "httpOnly": False, "secure": False})

    # 2. Format PostData (text + params list)
    post_data = None
    if request.method == "POST":
        content_text = request.content.decode("utf-8", errors="replace")
        post_data = {
            "mimeType": request.headers.get("content-type", "application/x-www-form-urlencoded"),
            "text": content_text,
            "params": [{"name": k, "value": v} for k, v in parse_qsl(content_text)]
        }

    # 3. Build the Schema
    return {
        "startedDateTime": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "time": int(response.elapsed.total_seconds() * 1000),
        "request": {
            "method": request.method,
            "url": str(request.url),
            "httpVersion": response.http_version,
            "cookies": req_cookies,
            "headers": [{"name": k, "value": v} for k, v in request.headers.items()],
            "queryString": [],
            "headersSize": len(str(request.headers)), # Approximated
            "bodySize": len(request.content),
            "postData": post_data
        },
        "response": {
            "status": response.status_code,
            "statusText": response.reason_phrase,
            "httpVersion": response.http_version,
            "cookies": [], # Usually parsed from 'set-cookie' if needed
            "headers": [{"name": k, "value": v} for k, v in response.headers.items()],
            "content": {
                "size": len(response.content),
                "mimeType": response.headers.get("content-type", "text/html"),
                "text": response.text
            },
            "redirectURL": str(response.headers.get("location", "")),
            "headersSize": len(str(response.headers)),
            "bodySize": len(response.content)
        },
        "cache": {},
        "timings": {
            "send": 0,
            "wait": int(response.elapsed.total_seconds() * 1000),
            "receive": 0,
            "connect": -1,
            "ssl": -1
        },
        "serverIPAddress": "" # Requires manual lookup or transport stream info
    }