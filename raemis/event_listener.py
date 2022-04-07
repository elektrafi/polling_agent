#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler as _BaseHTTPRequestHandler
from http.server import BaseHTTPRequestHandler as _BaseHTTPRequestHandler
from socketserver import ThreadingTCPServer as _ThreadingTCPServer
import time as _time
import pprint as _pprint
import threading as _threading
from urllib.parse import parse_qs as _parse_qs
import logging as _logging
import json as _json


class Listener:
    _logger = _logging.getLogger(__name__)
    _server_thread: _threading.Thread

    def start_event_receiver_server(self) -> None:
        try:
            self._eventReceiver = _ThreadingTCPServer(
                ("0.0.0.0", 9997), EventReceiver, bind_and_activate=True
            )
            self._server_thread = _threading.Thread(
                target=self._eventReceiver.serve_forever
            )
            self._eventReceiver.timeout = 3
            self._eventReceiver.block_on_close = False
            self._eventReceiver.request_queue_size = 25
            self._eventReceiver.daemon_threads = True
            self._server_thread.daemon = True
            self._server_thread.start()
            self._logger.info("event receiver server thread started")
        except:
            self._logger.exception("could not start event erceiver server")

    def __del__(self) -> None:
        self.done = True
        try:
            self._eventReceiver.server_close()
            self._eventReceiver.shutdown()
            self._logger.info("Event receiver HTTP server shutdown")
        except:
            self._logger.error("event receiver HTTP server failed to shutdown")


class EventReceiver(_BaseHTTPRequestHandler):
    _EVENT_PATH: str = "/events"
    _logger = _logging.getLogger(__name__)
    _last_time = _time.thread_time_ns()
    _this_time = _time.thread_time_ns()

    def posts_per_second(self):
        return 1e9 / (self._last_time - self._this_time)

    def update_time(self):
        self._last_time = self._this_time
        self._this_time = _time.thread_time_ns()

    def do_POST(self):
        if self._EVENT_PATH in self.path:
            self._logger.info("received event data from Raemis")
            data_len = self.headers.get("Content-Length")
            content_type = self.headers.get("Content-Type")
            data_len = int(data_len) if data_len else 0
            self.rfile.flush()
            post_data = self.rfile.read(data_len)
            post_data = _parse_qs(post_data, True, False)
            if b"imsi" not in post_data:
                self._logger.error(
                    f"no imsi in {post_data} aborting processing this record"
                )
                return
            imsis = post_data[b"imsi"]
            if b"add_text" not in post_data:
                self._logger.warn(
                    f'no "add_text" in {post_data} NOT aborting processing this record'
                )
            add_text = post_data[b"add_text"]
            if b"event_type" not in post_data:
                self._logger.error(
                    f"no event_type in {post_data} aborting processing this record"
                )
                return
            events = post_data[b"event_type"]
            if b"event_time" not in post_data:
                self._logger.warn(
                    f'no "event_time" in {post_data} NOT aborting processing this record'
                )
            event_times = post_data[b"event_time"]
            if (
                not imsis
                or not isinstance(imsis, list)
                or not add_text
                or not isinstance(add_text, list)
                or not events
                or not isinstance(events, list)
                or not event_times
                or not isinstance(event_times, list)
                or not "x-www-form-urlencoded" == content_type.lower().strip()
            ):
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", "0")
                self.end_headers()
                self.wfile.flush()
                self.connection.close()
                self._logger.error(
                    f"hit some kind of snag parsing the lists and content-type: {content_type}"
                )
                self._logger.error(
                    f"\tlists:\n\t{imsis}\n\t{add_text}\n\t{events}\n\t{event_times}"
                )
            event = data = event_time = imsi = ""
            try:
                event = events[0].decode().strip().lower()
                event_time = event_times[0].decode().strip().lower()
                imsi = imsis[0].decode().strip().lower()
                data = add_text[0].decode().strip().lower()
            except:
                self._logger.error("unable to parse POST data:")
                self._logger.error(f"event: {event}")
                self._logger.error(f"time: {event_time}")
                self._logger.error(f"imsi: {imsi}")
                self._logger.error(f"extra: {data}")
            if data:
                try:
                    data = _json.loads(data)
                except:
                    self._logger.error(f"unable to parse extra data ({data}) as JSON")
                    return
            try:
                event_time = _time.strptime(event_time, "%Y-%m-%d %H:%M:%S.%f")
            except:
                self._logger.warn(
                    f'unable to parse time {event_time} with format string "%Y-%m-%d %H:%M:%S.%f"'
                )
            if event == "pdp_context_activated":
                self._logger.info(f"parsing event: {event}")
                data = dict(data)
            elif event == "pdp_context_deactivated":
                self._logger.info(f"parsing event: {event}")
            else:
                self._logger.warn(f"event {event} not parsed")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(post_data)))
            self.end_headers()
            self.wfile.write(_pprint.pformat(post_data).encode())
            self.wfile.flush()
            self.connection.close()
            self._logger.info(
                f"Received {self.posts_per_second()} POST requests from Raemis per second"
            )
        return

    def do_GET(self):
        print("got stuff")
        self._logger.info("received GET event data from Raemis")
        obj = _json.dumps({"error": "incorrect method"})
        obj = obj.encode("utf-8")
        self.send_response(404)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(obj)
        self.connection.close()
        return
