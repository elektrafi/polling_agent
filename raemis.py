#!/usr/bin/env python3
import requests as rq


class Raemis:
    def __init__(self):
        self.api = "http://10.44.1.13/api/"
        self.api_user = "raemis"
        self.api_pass = "password"

    async def get_subscribers(self):
        endpoint = self.api + "subscriber"
        return rq.get(endpoint, auth=(self.api_user, self.api_pass)).json()

    async def get_data_sessions(self):
        endpoint = self.api + "data_session"
        return rq.get(endpoint, auth=(self.api_user, self.api_pass)).json()
