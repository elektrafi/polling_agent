#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler
from http.server import BaseHTTPRequestHandler
from socketserver import ThreadingTCPServer
import time
import pprint
import threading
from urllib.parse import parse_qs
import logging
import json
from ..sonar.ip_allocation import Allocator, Attachment


class Listener:
    logger = logging.getLogger(__name__)

    def start_event_receiver_server(self) -> None:
        try:
            self._eventReceiver = ThreadingTCPServer(
                ("0.0.0.0", 9997), EventReceiver, bind_and_activate=True
            )
            self.server_thread = threading.Thread(
                target=self._eventReceiver.serve_forever
            )
            self._eventReceiver.timeout = 3
            self._eventReceiver.block_on_close = False
            self._eventReceiver.request_queue_size = 25
            self._eventReceiver.daemon_threads = True
            self.server_thread.daemon = True
            self.server_thread.start()
            self.logger.info("event receiver server thread started")
        except:
            self.logger.exception("could not start event erceiver server")

    def __del__(self) -> None:
        self.done = True
        try:
            self._eventReceiver.server_close()
            self._eventReceiver.shutdown()
            self.logger.info("Event receiver HTTP server shutdown")
        except:
            self.logger.error("event receiver HTTP server failed to shutdown")


class EventReceiver(BaseHTTPRequestHandler):
    EVENT_PATH: str = "/events"
    logger = logging.getLogger(__name__)
    last_time = time.thread_time_ns()
    this_time = time.thread_time_ns()

    def posts_per_second(self):
        return 1e9 / (self.last_time - self.this_time)

    def update_time(self):
        self.last_time = self.this_time
        self.this_time = time.thread_time_ns()

    def do_POST(self):
        if self.EVENT_PATH in self.path:
            self.logger.info("received event data from Raemis")
            data_len = self.headers.get("Content-Length")
            content_type = self.headers.get("Content-Type")
            data_len = int(data_len) if data_len else 0
            self.rfile.flush()
            post_data = self.rfile.read(data_len)
            post_data = parse_qs(post_data, True, False)
            if b"imsi" not in post_data:
                self.logger.error(
                    f"no imsi in {post_data} aborting processing this record"
                )
                return
            imsis = post_data[b"imsi"]
            if b"add_text" not in post_data:
                self.logger.warn(
                    f'no "add_text" in {post_data} NOT aborting processing this record'
                )
            add_text = post_data[b"add_text"]
            if b"event_type" not in post_data:
                self.logger.error(
                    f"no event_type in {post_data} aborting processing this record"
                )
                return
            events = post_data[b"event_type"]
            if b"event_time" not in post_data:
                self.logger.warn(
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
                self.logger.error(
                    f"hit some kind of snag parsing the lists and content-type: {content_type}"
                )
                self.logger.error(
                    f"\tlists:\n\t{imsis}\n\t{add_text}\n\t{events}\n\t{event_times}"
                )
            event = data = event_time = imsi = ""
            try:
                event = events[0].decode().strip().lower()
                event_time = event_times[0].decode().strip().lower()
                imsi = imsis[0].decode().strip().lower()
                data = add_text[0].decode().strip().lower()
            except:
                self.logger.error("unable to parse POST data:")
                self.logger.error(f"event: {event}")
                self.logger.error(f"time: {event_time}")
                self.logger.error(f"imsi: {imsi}")
                self.logger.error(f"extra: {data}")
            if data:
                try:
                    data = json.loads(data)
                except:
                    self.logger.error(f"unable to parse extra data ({data}) as JSON")
                    return
            try:
                event_time = time.strptime(event_time, "%Y-%m-%d %H:%M:%S.%f")
            except:
                self.logger.warn(
                    f'unable to parse time {event_time} with format string "%Y-%m-%d %H:%M:%S.%f"'
                )
            if event == "pdp_context_activated":
                self.logger.info(f"parsing event: {event}")
                data = dict(data)
                attach = Attachment(imsi, event_time, data["ip"])
                Allocator.inst.add_pending_allocation(attach)
            elif event == "pdp_context_deactivated":
                self.logger.info(f"parsing event: {event}")
            else:
                self.logger.warn(f"event {event} not parsed")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(post_data)))
            self.end_headers()
            self.wfile.write(pprint.pformat(post_data).encode())
            self.wfile.flush()
            self.connection.close()
            self.logger.info(
                f"Received {self.posts_per_second()} POST requests from Raemis per second"
            )
        return

    def do_GET(self):
        print("got stuff")
        self.logger.info("received GET event data from Raemis")
        obj = json.dumps({"error": "incorrect method"})
        obj = obj.encode("utf-8")
        self.send_response(404)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(obj)
        self.connection.close()
        return
