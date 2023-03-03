import sys
import os
import time
import traceback

# Various utilities

def show(x):
    """Shows attribs of a object. Used for generating type hints!"""
    print("Attributes of", x)
    for k, v in x.__dict__.items():
        print(k, type(v))
    print("End of attributes")

def shortTrace(str, line=True, multiLines=True):
    """Print a very brief traceback. If "line" is true will print the line's text (without comments)"""
    s = traceback.extract_stack()[:-1]      # remove last item
    # find "main""
    start = 0
    for i, x in enumerate(s):
        fn = os.path.split(x.filename)
        if fn[-1] == 'main.py':
            start = i
            break
    s = s[start:]

    def delComm(ss):  # comments stripping, also processing "line"
        if line:
            if "#" in ss:
                return ss.rpartition('#')[0]
            else:
                return ss
        else:
            return ""

    s = [f"{os.path.basename(x.filename)}:{delComm(x.line)}[{x.lineno}]" for x in s]
    if multiLines:
        print(f"{str}::----------------------------------------------------")
        for x in s:
            print(f"    {x}")
    else:
        print(f"{str}:: "+" -> ".join(s))


def simpleExceptFormat(e: Exception):
    exc_type, exc_obj, exc_tb = sys.exc_info()
    fname = exc_tb.tb_frame.f_code.co_filename
    line = exc_tb.tb_lineno
    tp = exc_type.__name__
    msg = str(e)

    return f"Exception '{tp}' at {fname}:{line} - {msg}"


class Timer:
    def __init__(self, desc):
        self.desc = desc

    def __enter__(self):
        self.start = time.perf_counter()

    def __exit__(self, exc_type, exc_val, exc_tb):
        end = time.perf_counter()
        print(f"Timer {self.desc}: {end - self.start}")

    def start(self):
        self.start = time.perf_counter()

    def mark(self, txt):
        now = time.perf_counter()
        print(f"Timer {self.desc}/{txt}: {now - self.start}")
