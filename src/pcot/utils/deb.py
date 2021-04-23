# Various utilities

# Shows attribs of a object. Used for generating type hints!
def show(x):
    print("Attributes of",x)
    for k,v in x.__dict__.items():
        print(k,type(v))
    print("End of attributes")
