#!/usr/bin/env python3
import sys
import os
import pprint
import cgi
import cgitb

cgitb.enable()


print("<html><head></head><body>")

print("<h1>stdin</h1>")

cgi.print_arguments()

print("<br>")
print("<br>")


print("</body></html>")
