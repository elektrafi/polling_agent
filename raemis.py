#!/usr/bin/env python3
import requests as rq
from typing import Union


class Raemis:
    def __init__(self):
        self.api = "http://10.44.1.13/api/"

    def get_subscribers(self) -> list[dict]:
        endpoint = self.api + "subscriber"
        data = self.fetch_data(endpoint)
        return data if data else list()

    def get_data_sessions(self) -> list[dict]:
        endpoint = self.api + "data_session"
        data = self.fetch_data(endpoint)
        return data if data else list()

    def fetch_data(self, url: str) -> Union[None, list[dict]]:
        with rq.get(url=url, auth=("raemis", "password")) as resp:
            ret = resp.json()
        return ret if isinstance(ret, list) else None
    
    def get_subscriber_for_ip(self, ip: str) -> tuple[str, str]:
        
