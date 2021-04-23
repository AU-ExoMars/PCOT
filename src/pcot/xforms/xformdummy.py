from pcot.xform import XFormType, xformtype


@xformtype
class XFormDummy(XFormType):
    def __init__(self):
        super().__init__("dummy", "hidden", "0.0.0")

    def createTab(self, n, w):
        pass

    def init(self, n):
        pass

    def perform(self, n):
        pass
