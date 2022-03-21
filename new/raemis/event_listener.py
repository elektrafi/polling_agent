#!/usr/bin/env python3
from http.server import SimpleHTTPRequestHandler
import logging
import json


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
            # Raemis.event_queue.put(event_data)
            logger.debug(f"Raemis sent {data_len} bytes of data")
            self.wfile.write(b"OK")
        else:
            self.send_response_only(404, f"POST method not supported for {self.path}")
