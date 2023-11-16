import logging
import sys
import os
import time
import traceback


# Various utilities

logger = logging.getLogger(__name__)

from pcot import ui


def showAttributes(x):
    """Shows attribs of a object. Used for generating type hints!"""
    print("Attributes of", x)
    for k, v in x.__dict__.items():
        print(k, type(v))
    print("End of attributes")


def shortTrace(desc, line=True, multiLines=True):
    """Print a very brief traceback. If "line" is true will print the line's text (without comments)"""
    s = traceback.extract_stack()[:-1]  # remove last item
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
        print(f"{desc}::----------------------------------------------------")
        for x in s:
            print(f"    {x}")
    else:
        print(f"{desc}:: " + " -> ".join(s))


def simpleExceptFormat(e: Exception):
    exc_type, exc_obj, exc_tb = sys.exc_info()
    fname = exc_tb.tb_frame.f_code.co_filename
    line = exc_tb.tb_lineno
    tp = exc_type.__name__
    msg = str(e)

    return f"Exception '{tp}' at {fname}:{line} - {msg}"


class Timer:
    STDOUT = 0
    UILOG = 1
    STDLOG = 2

    def __init__(self, desc, show=STDLOG, enabled=True):
        """show can be STDOUT or UILOG, in which case it will use the standard output or the UI log; or a reference
        to a logger object (which must have a "info" method). If it is STDLOG, it will use the standard logger"""
        self.desc = desc
        self.prevTime = None
        self.startTime = None
        self.enabled = enabled
        self.show = show
        self.start()

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.mark("EXIT")

    def start(self):
        if self.enabled:
            self.startTime = time.perf_counter()
            self.prevTime = self.startTime

    def mark(self, txt):
        if self.enabled:
            now = time.perf_counter()
            d = now - self.prevTime
            if self.show == Timer.STDOUT:
                print(f"Timer {self.desc} {txt}: {d:.4f}, cum {now - self.startTime:.4f}")
            elif self.show == Timer.STDLOG:
                logger.info(f"Timer {self.desc} {txt}: {d:.4f}, cum {now - self.startTime:.4f}")
            elif self.show == Timer.UILOG:
                ui.log(f"Timer {self.desc} {txt}: {d:.4f}, cum {now - self.startTime:.4f}")
            elif isinstance(self.show, logging.Logger):
                self.show.info(f"Timer {self.desc} {txt}: {d:.4f}, cum {now - self.startTime:.4f}")

            self.prevTime = now
            return d
        return -1
