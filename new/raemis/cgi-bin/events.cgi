#!/usr/bin/env python3
import sys
import os
import pprint
import cgi
import cgitb

cgitb.enable()


print("<html><head></head><body>")

print("<h1>stdin</h1>")

while True:
    line = sys.stdin.buffer.readline()
    if not line:
        break
    print(line)
    print("<br>")

print("<br>")
print("<br>")

print("<h1>FieldStorage()</h1>")
form = cgi.FieldStorage()
keys = form.keys()
for k in keys:
    print(form[k])

print("</body></html>")
