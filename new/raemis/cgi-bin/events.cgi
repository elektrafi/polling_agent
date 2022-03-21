#!/usr/bin/env python3
import sys
import os
import pprint
import cgi
import cgitb

cgitb.enable()


print("<html><head></head><body>")

print("<h1>Environ</h1>")
cgi.print_environ()

print("<br>")
print("<br>")

print("<h1>environ_usage</h1>")
cgi.print_environ_usage()

print("<br>")
print("<br>")

print("<h1>data</h1>")
data = cgi.parse(strict_parsing=False, keep_blank_values=True)
print(data)

print("</body></html>")
