#
# Test basic library functionality
#
import os

import pcot

print("OK")

try:
    print(os.getcwd())
    g = pcot.load("../foo.pcot")
except FileNotFoundError:
    print("oops")
