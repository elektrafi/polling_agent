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

if sys.argv:
    pprint.pprint(sys.argv)


print("running")
