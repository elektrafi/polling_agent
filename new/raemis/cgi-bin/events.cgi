#!/usr/bin/env python3
import sys
import os
import pprint
import cgi
import cgitb

cgitb.enable()


print("<html><head></head><body>")

print("<h1>stdin</h1>")

data = sys.stdin.read()

print("<br>")
print("<br>")

print("<h1>data</h1>")
print(data)

print("</body></html>")
