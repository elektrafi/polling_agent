#!/usr/bin/env python3
import sys
import os
import pprint
import cgi
import cgitb

cgitb.enable()

cgi.print_environ()
cgi.print_arguments()
cgi.print_directory()

print()
print()

form = cgi.parse(keep_blank_values=True, strict_parsing=False)
pprint.pprint(form)

print()
print()


form = cgi.FieldStorage()
keys = form.keys()
for k in keys:
    print(form[k])
