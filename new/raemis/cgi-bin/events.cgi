#!/usr/bin/env python3
import sys
import os
import pprint
import cgi
import cgitb

cgitb.enable()

form = cgi.FieldStorage()


cgi.print_environ()
cgi.print_arguments()
cgi.print_directory()
cgi.print_environ()
cgi.print_form(dict(form))

if sys.argv:
    pprint.pprint(sys.argv)

for param in os.environ.keys():
    print("<b>%20s</b>: %s<\br>" % (param, os.environ[param]))

print("running")
