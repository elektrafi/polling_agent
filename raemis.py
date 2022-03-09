#!/usr/bin/env python3
import requests
import json
import logging
import threading
from http.server import (
    ThreadingHTTPServer,
    SimpleHTTPRequestHandler,
)
from typing import Callable, Union
from enum import Enum, unique
import multiprocessing


@unique
class RaemisEndpoint(Enum):
    SUBSCRIBERS = "subscriber"
    SESSION = "session"
    DATA_SESSIONS = "data_session"


@unique
class HTTPMethod(Enum):
    GET = "GET"
    DELETE = "DELETE"
    POST = "POST"


class Raemis:
    event_queue = multiprocessing.Queue()

    def __init__(
        self,
        apiUrl: str = "http://10.44.1.13/api",
        username: str = "pollingAgent",
        password: str = "EFI_Buna2020!1",
    ) -> None:
        self.logger = logging.getLogger(__name__)
        self.session = requests.session()
        self.session.verify = False
        self.apiUrl = apiUrl[:-1] if apiUrl[-1] == "/" else apiUrl
        self._auth = {"username": username, "password": password}
        self._post_data(RaemisEndpoint.SESSION, self._auth)

    def event_receiver(self) -> None:
        self._start_event_receiver_server()
        self.logger.info("initialized raemis API connection")

    def _start_event_receiver_server(self) -> None:
        try:
            self._eventReceiver = ThreadingHTTPServer(("0.0.0.0", 9999), EventReceiver)
            server_thread = threading.Thread(target=self._eventReceiver.serve_forever)
            server_thread.daemon = True
            server_thread.start()
            self.logger.info("event receiver server thread started")
        except:
            self.logger.exception("could not start event erceiver server")

    def __del__(self) -> None:
        try:
            self._eventReceiver.shutdown()
            self.logger.info("Event receiver HTTP server shutdown")
        except:
            self.logger.error("event receiver HTTP server failed to shutdown")
        try:
            self._del_data(RaemisEndpoint.SESSION, self._auth)
            self.logger.info("Raemis informed of session end")
        except:
            self.logger.error(
                "deleting session from Raemis timed out (but still probably deleted the record)"
            )
        self.session.close()
        self.logger.info("HTTP API session to Raemis closed")

    def get_subscribers(self) -> Union[None, list[dict]]:
        data = None
        try:
            data = self._get_data(RaemisEndpoint.SUBSCRIBERS).json()
        finally:
            self.logger.debug(
                f'returning {len(data) if data is not None else "N/A"} subscribers'
            )
        return data

    def get_data_sessions(self) -> Union[None, list[dict]]:
        data = None
        try:
            data = self._get_data(RaemisEndpoint.DATA_SESSIONS).json()
        finally:
            self.logger.debug(
                f'returning {len(data) if data is not None else "N/A"} data session records'
            )
        return data

    def _get_raemis_url(self, ep: RaemisEndpoint) -> str:
        return f"{self.apiUrl}/{ep.value}"

    def _del_data(
        self, ep: RaemisEndpoint, data: dict[str, str] = {}
    ) -> requests.Response:
        return self._request(HTTPMethod.DELETE, ep, data)

    def _post_data(
        self, ep: RaemisEndpoint, data: dict[str, str] = {}
    ) -> requests.Response:
        return self._request(HTTPMethod.POST, ep, data)

    def _get_data(self, ep: RaemisEndpoint) -> requests.Response:
        return self._request(HTTPMethod.GET, ep)

    def _request(
        self, method: HTTPMethod, ep: RaemisEndpoint, data: dict[str, str] = {}
    ) -> requests.Response:
        timeout = 1
        resp = None
        while resp is None:
            try:
                resp = self.session.request(
                    method.value,
                    self._get_raemis_url(ep),
                    timeout=timeout,
                    data=data if data else None,
                )
            except:
                if timeout > 4:
                    self.logger.error(
                        f"unable to resolve HTTP {method.value} request to {self._get_raemis_url(ep)}"
                    )
                    raise requests.ConnectionError
            finally:
                timeout += 3
        self.logger.debug(
            f"HTTP request type {method.value} resolved with status code {resp.status_code}"
        )
        return resp


class EventReceiver(SimpleHTTPRequestHandler):
    EVENT_PATH: str = "/events"

    def do_POST(self):
        if self.path == self.EVENT_PATH:
            logger = logging.getLogger(__name__)
            logger.info("received event data from Raemis")
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            data_len = int(self.headers.get("Content-Length"))
            post_data = self.rfile.read(data_len)
            event_data = json.loads(post_data)
            Raemis.event_queue.put(event_data)
            logger.debug(f"Raemis sent {data_len} bytes of data")
            self.wfile.write(b"OK")
        else:
            self.send_response_only(404, f"POST method not supported for {self.path}")
