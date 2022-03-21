#!/usr/bin/env python3
from http.server import SimpleHTTPRequestHandler
from http.server import ThreadingHTTPServer
import threading
import socket
import logging
import json


class RaemisListener:
    logger = logging.getLogger(__name__)

    def sock(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("0.0.0.0", 9999))
            s.listen()
            conn, addr = s.accept()
            print(conn)
            print(addr)
            with conn:
                print(f"Connected by {addr}")
                while True:
                    data = conn.recv(1024)
                    if not data:
                        break
                    print(str(data))
                    conn.sendall(data)

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
            import pprint

            pprint.pprint(post_data)
            # Raemis.event_queue.put(event_data)
            logger.debug(f"Raemis sent {data_len} bytes of data")
            self.wfile.write(b"OK")
        else:
            self.send_response_only(404, f"POST method not supported for {self.path}")

    def do_GET(self):
        print("got stuff")
        self.wfile.write(b"DATA")
