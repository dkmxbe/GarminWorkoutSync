import http
import json
import logging
import os
import re
import sys

import requests

# ++
# Many thanks to petergardfjall/garminexport
# --

class GarminClient(object):

    SSO_LOGIN_URL = "https://sso.garmin.com/sso/login"
    """Garmin Connect's Single-Sign On login URL."""
    SSO_SIGNIN_URL = "https://sso.garmin.com/sso/signin"
    """The Garmin Connect Single-Sign On sign-in URL. This is where the login form
    gets POSTed."""

    _WORKOUT_SERVICE_URL = "https://connect.garmin.com/proxy/workout-service"
    _CALENDAR_SERVICE_URL = "https://connect.garmin.com/proxy/calendar-service"

    _REQUIRED_HEADERS = {
        "nk": "NT"
    }

    _LOG = logging.getLogger(__name__)

    def __init__(self, username, password, cookie_jar):
        self.username = username
        self.password = password
        self.cookie_jar = cookie_jar
        self.session = None

    def __enter__(self):
        self._connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._disconnect()

    def list_workouts(self, batch_size=100):
        assert self.session

        for start_index in range(0, sys.maxsize, batch_size):
            params = {
                "start": start_index,
                "limit": batch_size
            }
            """ Other param options
                "myWorkoutsOnly": "true",
                "sharedWorkoutsOnly": "true",
                "orderBy": "WORKOUT_NAME",
                "orderSeq": "ASC",
                "includeAtp": "false"
            """
            response = self.session.get(GarminClient._WORKOUT_SERVICE_URL + "/workouts", params=params)
            response.raise_for_status()

            response_jsons = json.loads(response.text)
            if not response_jsons or response_jsons == []:
                break

            for response_json in response_jsons:
                yield response_json

    def get_workout(self, workout_id):
        assert self.session

        response = self.session.get(GarminClient._WORKOUT_SERVICE_URL + "/workout/%s" % workout_id)
        response.raise_for_status()

        return json.loads(response.text)
    
    def schedule(self, workout_id, str_date):
        assert self.session

        item = { "date": str_date }
        
        response = self.session.post(GarminClient._WORKOUT_SERVICE_URL + "/schedule/%s" % workout_id,
                                     headers=GarminClient._REQUIRED_HEADERS, json=item)
        response.raise_for_status()

        return json.loads(response.text)

    def get_schedule(self, year, month):
        assert self.session
        
        response = self.session.get(GarminClient._CALENDAR_SERVICE_URL + "/year/%s/month/%s" % (year, month - 1))
        response.raise_for_status()

        return json.loads(response.text)

    def download_workout(self, workout_id, file):
        assert self.session

        response = self.session.get(GarminClient._WORKOUT_SERVICE_URL + "/workout/FIT/%s" % workout_id)
        response.raise_for_status()

        with open(file, "wb") as f:
            f.write(response.content)

    def save_workout(self, workout):
        assert self.session

        response = self.session.post(GarminClient._WORKOUT_SERVICE_URL + "/workout",
                                     headers=GarminClient._REQUIRED_HEADERS, json=workout)
        response.raise_for_status()

        return json.loads(response.text)

    def update_workout(self, workout_id, workout):
        assert self.session

        response = self.session.put(GarminClient._WORKOUT_SERVICE_URL + "/workout/%s" % workout_id,
                                    headers=GarminClient._REQUIRED_HEADERS, json=workout)
        response.raise_for_status()

    def delete_workout(self, id):
        assert self.session

        response = self.session.delete(GarminClient._WORKOUT_SERVICE_URL + "/workout/%s" % id,
                                       headers=GarminClient._REQUIRED_HEADERS)
        response.raise_for_status()

    def _connect(self):
        self.session = requests.Session()
        self.session.cookies = http.cookiejar.LWPCookieJar(self.cookie_jar)

        if os.path.isfile(self.cookie_jar):
            self.session.cookies.load(ignore_discard=True, ignore_expires=True)

        response = self.session.get("https://connect.garmin.com/modern/settings", allow_redirects=False)
        if response.status_code != 200:
            self._LOG.info("Authenticate user '%s'", self.username)
            self._authenticate()
        else:
            self._LOG.info("User '%s' already authenticated", self.username)

    def _disconnect(self):
        if self.session:
            self.session.cookies.save(ignore_discard=True, ignore_expires=True)
            self.session.close()
            self.session = None

    def _authenticate(self):
        assert self.session

        form_data = {
            "username": self.username,
            "password": self.password,
            "embed": "false",
            "_csrf": self._get_csrf_token(),
        }

        headers = {
            'origin': 'https://sso.garmin.com',
            # We need to set a fake ua. Garmin blocks default python ua
            'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux i686 on x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2811.59 Safari/537.36'
        }
    
        auth_response = self.session.post(
            GarminClient.SSO_SIGNIN_URL, headers=headers, params=self._auth_params(), data=form_data)
        auth_response.raise_for_status()

        self._LOG.debug("got auth response: %s", auth_response.text)
        
        auth_ticket_url = self._extract_auth_ticket_url(auth_response.text)

        self._LOG.debug("auth ticket url: '%s'", auth_ticket_url)

        self._LOG.info("claiming auth ticket ...")
        response = self.session.get(auth_ticket_url)
        response.raise_for_status()

        # appears like we need to touch base with the main page to complete the
        # login ceremony.
        self.session.get('https://connect.garmin.com/modern')

    def _auth_params(self):
        """A set of request query parameters that need to be present for Garmin to
        accept our login attempt.
        """
        return {
            "service": "https://connect.garmin.com/modern/",
            "gauthHost": "https://sso.garmin.com/sso",
        }

    def _get_csrf_token(self):
        """Retrieves a Cross-Site Request Forgery (CSRF) token from Garmin's login
        page. The token is passed along in the login form for increased
        security."""
        self._LOG.info("fetching CSRF token ...")
        resp = self.session.get(GarminClient.SSO_LOGIN_URL, params=self._auth_params())
        if resp.status_code != 200:
            raise ValueError("auth failure: could not load {}".format(GarminClient.SSO_LOGIN_URL))
        # extract CSRF token
        csrf_token = re.search(r'<input type="hidden" name="_csrf" value="(\w+)"', resp.content.decode('utf-8'))
        if not csrf_token:
            raise ValueError("auth failure: no CSRF token in {}".format(GarminClient.SSO_LOGIN_URL))
        return csrf_token.group(1)
    
    def _extract_auth_ticket_url(auth_response):
        match = re.search(r'response_url\s*=\s*"(https:[^"]+)"', auth_response)
        if not match:
            raise Exception("Unable to extract auth ticket URL from:\n%s" % auth_response)
        auth_ticket_url = match.group(1).replace("\\", "")
        return auth_ticket_url