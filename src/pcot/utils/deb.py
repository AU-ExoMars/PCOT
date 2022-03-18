import sys
import time


# Various utilities

def show(x):
    """Shows attribs of a object. Used for generating type hints!"""
    print("Attributes of", x)
    for k, v in x.__dict__.items():
        print(k, type(v))
    print("End of attributes")


def simpleExceptFormat(e: Exception):
    exc_type, exc_obj, exc_tb = sys.exc_info()
    fname = exc_tb.tb_frame.f_code.co_filename
    line = exc_tb.tb_lineno
    tp = exc_type.__name__
    msg = str(e)

    return f"Exception '{tp}' at {fname}:{line} - {msg}"


class Timer:
    def __init__(self,desc):
        self.desc = desc

    def __enter__(self):
        self.start = time.time()

    def __exit__(self, exc_type, exc_val, exc_tb):
        end = time.time()
        print(f"Timer {self.desc}: {end - self.start}")
