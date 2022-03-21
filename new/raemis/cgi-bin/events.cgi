#!/usr/bin/env python3
import sys
import os
import pprint
import cgi
import cgitb

cgitb.enable()
cgi.print_arguments()

print("<html><head></head><body>")

print("<br>")
print("<br>")

print("<h1>FieldStorage()</h1>")
form = cgi.FieldStorage()
keys = form.keys()
for k in keys:
    print(form[k])

print("</body></html>")
