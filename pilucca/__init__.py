import datetime
import json
import logging
import os
import time
import uuid
from datetime import date
from typing import List

from httpx import Client, URL, Response

from pilucca.conf import settings
from pilucca.har import create_har_entry
from pilucca.models import AuthToken, LuccaUserInfo, LuccaAuthToken, UserInputConfiguration, WorkLocationTimeline, \
    PrincipalResponse, WorkLocationFromTemplate
from pilucca.utils import hook_response, hash_sha256

logger = logging.getLogger(__name__)


class ILuccaClient:
    BASE_AUTH = 'https://accounts.world.luccasoftware.com'

    def __init__(self):
        self.instance_url: str | None = None
        self.auth_token: AuthToken | None = None
        self.lucca_auth_token: LuccaAuthToken | None = None
        self.lucca_user_info: LuccaUserInfo | None = None
        self._har_entries: List[dict]  =  []

        client_hooks = {
            "request": [],
            "response": [],
        }

        response_hooks = []

        if settings.DEBUG:
            response_hooks.append(hook_response)

        if settings.HTTPX_HAR_ENABLED:
            response_hooks.append(self.hook_har_entry)

        client_hooks["response"] = response_hooks

        self.client = Client(
            http2=True,
            verify=False,
            follow_redirects=True,
            event_hooks=client_hooks
        )

    def hook_har_entry(self, response: Response):
        self._har_entries.append(create_har_entry(response=response))

    def write_har_file(self):
        if not settings.HTTPX_HAR_ENABLED:
            return
        # Wrap in the final HAR structure
        har_data = {
            "log": {
                "version": "1.2",
                "creator": {"name": "Httpx-Har-Gen", "version": "1.0"},
                "entries": self._har_entries
            }
        }

        har_name = f'pilucca_{datetime.datetime.now().strftime("%Y%m%d%H%M%S")}.json'
        har_file = os.path.join(settings.HTTPX_HAR_PATH, har_name)
        with open(har_file, "w") as f:
            json.dump(har_data, f, indent=2)

    def login(self):
        logger.info(f"Generating token")
        logger.info(f"Register device")
        url = f"{self.BASE_AUTH}/backoffice/services/mobile-applications/register"
        payload = {
            "type": "lucca"
        }
        response = self.client.post(url, json=payload)

        client_id = response.json()["clientId"]

        logger.info(f"Loading Oauth")
        challenge_url = f'{self.BASE_AUTH}/connect/authorize'

        code_verifier = str(uuid.uuid4())
        challenge = hash_sha256(code_verifier)

        query_params = {
            'client_id': client_id,
            'code_challenge': challenge,
            'code_challenge_method': 'S256',
            'redirect_uri': 'timmi://login/oauth-callback',
            'scope': 'profile generate.authtoken offline_access devices.write',
            'response_type': 'code',
            'state': str(uuid.uuid4()),
            'prompt': '',
        }
        challenge_response = self.client.get(challenge_url, params=query_params)
        logger.info(f"Challenge status_code: {challenge_response.status_code}")

        # retrieve XSRF-COOKIE
        user_url = f'{self.BASE_AUTH}/api/user-accounts/login'
        head_response = self.client.head(user_url)
        logger.info(f"Head response: {head_response.status_code}")


        login_url = f'{self.BASE_AUTH}/api/user-accounts/login/password'
        login_payload = {
            "identifier": settings.ILUCCA_USERNAME,
            "password": settings.ILUCCA_PASSWORD
        }

        referer = challenge_response.url.raw_path.decode().replace('/login', f'{self.BASE_AUTH}/login/factors/password')
        c = dict(challenge_response.cookies)
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Mobile Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/json",
            "X-CSRF-TOKEN": c.get('XSRF-TOKEN'),
            "Sec-CH-UA": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
            "Sec-CH-UA-Mobile": "?1",
            "Sec-CH-UA-Platform": '"Android"',
            "Origin": self.BASE_AUTH,
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": referer,
            "Accept-Encoding": "gzip, deflate, br, zstd",
        }
        time.sleep(3)
        login_response = self.client.post(login_url, json=login_payload, headers=headers)
        login_response_json = login_response.json()
        logger.info(f"Login Success: {login_response_json.get('status')}, Domain: {login_response_json.get('instanceUrl')}")
        self.instance_url = login_response.json()['instanceUrl']

        principal_url = f'{self.BASE_AUTH}/api/principal'
        principal_response = self.client.get(principal_url)
        logger.info(f"Principal response: {principal_response.status_code}")

        # Remember-me (the cookie will be extended 1 month)
        remember_url = f'{self.BASE_AUTH}/api/user-accounts/login/session/remember-me'
        remember_response = self.client.post(remember_url, headers=headers)

        # Once we have the login ok, we need the token
        authorize_response = self.client.get(challenge_url, params=query_params, follow_redirects=False)
        location = URL(authorize_response.headers.get('location'))
        code = location.params.get('code')
        state = location.params.get('state')
        iss = location.params.get('iss')

        # get token
        connect_token_url = f'{self.BASE_AUTH}/connect/token'
        token_payload = {
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': client_id,
            'redirect_uri': 'timmi://login/oauth-callback',
            'code_verifier': code_verifier

        }
        headers = {
            'content-type': 'application/x-www-form-urlencoded',
            'accept': 'application/json',
            'user-agent': 'Lucca/4.9.9(231) Dalvik/2.1.0 (Linux; U; Android 16; Pixel 6a Build/BP4A.251205.006)',
            'accept-encoding': 'gzip'
        }
        token_response = self.client.post(connect_token_url, data=token_payload, headers=headers)
        self.auth_token = AuthToken(**token_response.json())
        self._reset_client_headers(f'{self.auth_token.token_type} {self.auth_token.access_token}')
        self.base_user_info()
        self.base_get_token()

    def _reset_client_headers(self, access_token: str):
        self.client.headers.clear()
        self.client.headers.update({
            'authorization': access_token,
            'accept': 'application/json',
            'accept-encoding': 'gzip',
            'user-agent': 'Lucca/4.9.9(231) Dalvik/2.1.0 (Linux; U; Android 16; Pixel 6a Build/BP4A.251205.006)',
        })

    def base_user_info(self) -> LuccaUserInfo:
        user_info_url = f'{self.BASE_AUTH}/userinfo'
        user_info_response = self.client.get(user_info_url)
        self.lucca_user_info =  LuccaUserInfo(**user_info_response.json())
        return self.lucca_user_info

    def base_get_token(self):
        url = f'{self.BASE_AUTH}/services/generate-auth-token'
        response = self.client.post(url, json={})
        self.lucca_auth_token = LuccaAuthToken(**response.json())
        self._reset_client_headers(access_token=f'Lucca user={self.lucca_auth_token.authToken}')

    def principal(self):
        url = f'{self.instance_url}/identity/api/principal'
        response = self.client.get(url)
        return PrincipalResponse(**response.json())

    def office_work_location_authorized_interval(self):
        url = f'{self.instance_url}/work-locations/mobile/api/schedule/user-input-configuration'
        response = self.client.get(url)
        return UserInputConfiguration(**response.json())

    def office_work_location_timeline(self, user_id: int, start_date: date, end_date: date):
        url = f'{self.instance_url}/work-locations/mobile/api/timeline?userId={user_id}&start={start_date}&end={end_date}'
        response = self.client.get(url)
        return WorkLocationTimeline(**response.json())

    def office_work_location_from_week_template(self, start):
        url = f'{self.instance_url}/work-locations/mobile/api/user-locations/from-week-template?date={start}&byPassWarnings=false'
        response = self.client.post(url, data=None)
        return WorkLocationFromTemplate(**response.json())

    def info(self):
        url = f'{self.instance_url}/directory/api/employees'
        response = self.client.get(url)
        logger.info(f"Employees response: {json.dumps(response.json(), indent=2)}")