class HTML:
    """This is a simple HTML formatting class. I could probably use ElementTree for this, to be honest,
    but this has some nice features such as the visit method."""
    def __init__(self, tag, *args, attrs=None):
        self.model = []
        self.tag = tag
        if attrs is None:
            attrs = dict()
        self.attrs = attrs
        for x in args:
            if isinstance(x, list):
                self.model += x
            else:
                self.model.append(x)

    def _getOpeningTag(self):
        attrs = " ".join(['{}="{}"'.format(k, v) for k, v in self.attrs.items()])
        return "<{} {}>".format(self.tag, attrs)

    def _getClosingTag(self):
        return "</{}>".format(self.tag)

    def string(self, makeTags=True):
        out = self._getOpeningTag() if makeTags else ""
        for x in self.model:
            if isinstance(x, HTML):
                out += x.string(makeTags)
            else:
                out += str(x)
        out += self._getClosingTag() if makeTags else ""
        return out

    def _visit(self, fn):
        fn(self)
        for x in self.model:
            if isinstance(x, HTML):
                x._visit(fn)

    def visit(self,fn):
        self._visit(fn)
        return self


class Col(HTML):
    def __init__(self, col, *args):
        super().__init__("font", *args, attrs={"color": col})


class Bold(HTML):
    def __init__(self,*args):
        super().__init__("b", *args)


BR = "<br/"



