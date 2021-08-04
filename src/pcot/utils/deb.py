import time


# Various utilities

# Shows attribs of a object. Used for generating type hints!
def show(x):
    print("Attributes of", x)
    for k, v in x.__dict__.items():
        print(k, type(v))
    print("End of attributes")


class Timer:
    def __init__(self,desc):
        self.desc = desc

    def __enter__(self):
        self.start = time.time()

    def __exit__(self, exc_type, exc_val, exc_tb):
        end = time.time()
        print(f"Timer {self.desc}: {end - self.start}")
