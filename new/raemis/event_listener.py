#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
import pprint
import threading
import socket
import logging
import json


class RaemisListener:
    logger = logging.getLogger(__name__)

    def sock(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("0.0.0.0", 9998))
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
            self._eventReceiver = ThreadingHTTPServer(
                ("10.244.1.250", 9998), EventReceiver
            )
            self.server_thread = threading.Thread(
                target=self._eventReceiver.serve_forever
            )
            self.server_thread.daemon = False
            self.server_thread.start()
            self.logger.info("event receiver server thread started")
        except:
            self.logger.exception("could not start event erceiver server")

    def __del__(self) -> None:
        try:
            self._eventReceiver.server_close()
            self._eventReceiver.shutdown()
            self.logger.info("Event receiver HTTP server shutdown")
        except:
            self.logger.error("event receiver HTTP server failed to shutdown")


class EventReceiver(BaseHTTPRequestHandler):
    EVENT_PATH: str = "/events"
    logger = logging.getLogger(__name__)

    def do_POST(self):
        print("post")
        if self.path == self.EVENT_PATH:
            print("path")
            self.logger.info("received event data from Raemis")
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            print("headers")
            data_len = self.headers.get("Content-Length")
            data_len = data_len if data_len else 0
            post_data = self.rfile.read(data_len)
            print("data: ", post_data)
            # event_data = json.loads(post_data)

            pprint.pprint(post_data)
            print("printed data")
            # Raemis.event_queue.put(event_data)
            self.logger.debug(f"Raemis sent {data_len} bytes of data")
            print("done")
        else:
            print("not path")
            self.logger.info("received event data from Raemis")
            self.send_response(404)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"nopage")

    def do_GET(self):
        print("got stuff")
        self.logger.info("received GET event data from Raemis")
        self.send_response(404)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"nomethod")
