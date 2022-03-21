#!/usr/bin/env python3
from flask import Flask, make_response, request


def create_listener():
    app = Flask(__name__)

    @app.route("/events", methods=["GET", "POST"])
    def events():
        print(request.base_url)
        print(request.args)
        print(request.data)
        print(request.form)
        print(request.values)
        if request.is_json:
            print(request.json)
        r = make_response()
        r.set_data("Done")

    return app
