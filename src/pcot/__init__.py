import configparser,os,io
from pkg_resources import resource_string as resource_bytes


def getAssetAsFile(fn):
    s = resource_bytes('pcot.assets',fn).decode('utf-8')
    return io.StringIO(s)


config = None

config = configparser.ConfigParser()
config.read_file(getAssetAsFile('defaults.ini'))
config.read(['site.cfg', os.path.expanduser('~/.pcot.ini')], encoding='utf_8')


print("INIT")
