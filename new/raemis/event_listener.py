#!/usr/bin/env python3
from http.server import (
    BaseHTTPRequestHandler,
    SimpleHTTPRequestHandler,
    CGIHTTPRequestHandler,
)
from http.server import ThreadingHTTPServer
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import TCPServer, ThreadingTCPServer
import cgi
import time
import socketserver
import pprint
import threading
from urllib.parse import urlparse
from urllib.parse import parse_qs
import socket
import logging
import json


class RaemisListener:
    logger = logging.getLogger(__name__)

    def start_socket(self):
        sock = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, None
        )
        sock.bind(("0.0.0.0", 9997))
        sock.listen(10)
        while True:
            (clientsock, addr) = sock.accept()
            threading.Thread(
                name=f"client-{addr}", target=self.child_socket, args=[clientsock, addr]
            )

    def child_socket(self, sock: socket.socket, addr: str):
        chunks = []
        bytes_recd = 0
        MSGLEN = 2048
        while bytes_recd < MSGLEN:
            chunk = sock.recv(min(MSGLEN - bytes_recd, 2048))
            if chunk == b"":
                raise RuntimeError("socket connection broken")
            chunks.append(chunk)
            bytes_recd = bytes_recd + len(chunk)
        return b"".join(chunks)

    def _start_event_receiver_server(self) -> None:
        try:
            self._eventReceiver = ThreadingTCPServer(
                ("0.0.0.0", 9997), EventReceiver, bind_and_activate=True
            )
            self.server_thread = threading.Thread(
                target=self._eventReceiver.serve_forever
            )
            self._eventReceiver.timeout = 10
            self.server_thread.daemon = True
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
    last_time = time.thread_time_ns()
    this_time = time.thread_time_ns()

    def posts_per_second(self):
        return 1 / (self.this_time - self.last_time)

    def update_time(self):
        self.last_time = self.this_time
        self.this_time = time.thread_time_ns()

    def do_POST(self):
        print("post")
        if self.EVENT_PATH in self.path:
            print("path")
            self.logger.info("received event data from Raemis")
            print("headers")
            data_len = self.headers.get("Content-Length")
            data_len = int(data_len) if data_len else 0
            self.rfile.flush()
            post_data = self.rfile.read(data_len)
            # event_data = json.loads(post_data)
            post_data = parse_qs(post_data, True, False)
            pprint.pprint(post_data)
            print("printed data")
            # Raemis.event_queue.put(event_data)
            query_components = parse_qs(urlparse(self.path).query)
            self.logger.debug(f"Other parser:\t{query_components}")
            self.logger.debug(f"headers:\t{pprint.pformat(self.headers.as_string())}")
            self.logger.debug(f"Raemis sent {data_len} bytes of data")
            print("done")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(post_data)))
            self.end_headers()
            self.wfile.write(pprint.pformat(post_data).encode())
            self.wfile.flush()
            self.connection.close()
            self.update_time()
            return

        else:
            print("not path")
            obj = json.dumps({"error": "incorrect page"})
            obj = obj.encode("utf-8")
            self.logger.info("received event data from Raemis")
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(obj)))
            self.end_headers()
            self.wfile.write(obj)
            self.connection.close()
            self.update_time()
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
