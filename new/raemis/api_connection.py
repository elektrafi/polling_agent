#!/usr/bin/env python3
import requests
from ..model.ue import UE, Client
import logging
from typing import Union
from enum import Enum, unique


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
    # event_queue = multiprocessing.Queue()
    logger = logging.getLogger(__name__)
    session: requests.Session
    apiUrl: str

    def __init__(
        self,
        apiUrl: str = "http://10.44.1.13/api",
        username: str = "pollingAgent",
        password: str = "EFI_Buna2020!1",
    ) -> None:
        self.logger.info("starting Raemis API connection")
        self.session = requests.session()
        self.session.verify = False
        self.session.auth = (username, password)
        self.apiUrl = apiUrl[:-1] if apiUrl[-1] == "/" else apiUrl
        self._auth = {"username": username, "password": password}
        self._post_data(RaemisEndpoint.SESSION, self._auth)

    # def event_receiver(self) -> None:
    #    self._start_event_receiver_server()
    #    self.logger.info("initialized raemis API connection")

    # def _start_event_receiver_server(self) -> None:
    #    try:
    #        self._eventReceiver = ThreadingHTTPServer(("0.0.0.0", 9999), EventReceiver)
    #        server_thread = threading.Thread(target=self._eventReceiver.serve_forever)
    #        server_thread.daemon = True
    #        server_thread.start()
    #        self.logger.info("event receiver server thread started")
    #    except:
    #        self.logger.exception("could not start event erceiver server")

    def __del__(self) -> None:
        try:
            # self._eventReceiver.shutdown()
            self.logger.info("Event receiver HTTP server shutdown")
        except:
            self.logger.error("event receiver HTTP server failed to shutdown")
        self.session.close()
        self.logger.info("HTTP API session to Raemis closed")

    def get_subscribers(self) -> list[UE]:
        data = None
        try:
            data = self._get_data(RaemisEndpoint.SUBSCRIBERS).json()
        finally:
            self.logger.info(
                f'returning {len(data) if data is not None else "N/A"} subscribers'
            )
        return self._convert_api_subscribers_to_ue(data)

    def get_data_sessions(self) -> Union[None, list[dict]]:
        data = None
        try:
            data = self._get_data(RaemisEndpoint.DATA_SESSIONS).json()
        finally:
            self.logger.info(
                f'returning {len(data) if data is not None else "N/A"} data session records'
            )
        return data

    def _convert_api_subscribers_to_ue(self, json: list[dict[str, str]]) -> list[UE]:
        return [
            self._convert_api_subscriber_to_ue(x)
            for x in json
            if "imei" in x and x["imei"]
        ]

    def _convert_api_subscriber_to_ue(self, json: dict[str, str]) -> UE:
        equip = UE()
        equip.imei = json["imei"]
        equip.imsi = json["imsi"]
        equip.cell_id = json["cell_id"]
        equip.sim_index = json["msisdn"]
        equip._raemis_id = json["msisdn"]
        equip.attached = json["local_ps_attachment"].lower().strip() == "attached"
        equip.client = Client(json["name"])
        return equip

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
                if timeout > 60:
                    self.logger.error(
                        f"unable to resolve HTTP {method.value} request to {self._get_raemis_url(ep)}"
                    )
                    raise requests.ConnectionError
            finally:
                timeout += 5
        self.logger.debug(
            f"HTTP request type {method.value} resolved with status code {resp.status_code}"
        )
        return resp
