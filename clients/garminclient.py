import http
import json
import logging
import os
import re
import sys

import requests

class GarminClient(object):
    _SSO_LOGIN_URL = "https://sso.garmin.com/sso/signin"
    _WORKOUT_SERVICE_URL = "https://connect.garmin.com/modern/proxy/workout-service"
    _CALENDAR_SERVICE_URL = "https://connect.garmin.com/modern/proxy/calendar-service"

    _REQUIRED_HEADERS = {
        "Referer": "https://connect.garmin.com/modern/workouts",
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
        # https://connect.garmin.com/modern/proxy/calendar-service/year/2020/month/10/day/5/start/1
        # response = self.session.get(GarminClient._CALENDAR_SERVICE_URL + "/year/%s/month/%s/day/%s/start/1" % (year, month - 1, day))
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
            "embed": "false"
        }
        request_params = {
            "service": "https://connect.garmin.com/modern"
        }
        headers = {'origin': 'https://sso.garmin.com'}

        auth_response = self.session.post(
            GarminClient._SSO_LOGIN_URL, headers=headers, params=request_params, data=form_data)
        auth_response.raise_for_status()

        auth_ticket_url = self._extract_auth_ticket_url(auth_response.text)

        response = self.session.get(auth_ticket_url)
        response.raise_for_status()

    @staticmethod
    def _extract_auth_ticket_url(auth_response):
        match = re.search(r'response_url\s*=\s*"(https:[^"]+)"', auth_response)
        if not match:
            raise Exception("Unable to extract auth ticket URL from:\n%s" % auth_response)
        auth_ticket_url = match.group(1).replace("\\", "")
        return auth_ticket_url