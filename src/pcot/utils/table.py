import csv
import io
from collections import OrderedDict

import numpy as np

from pcot.sources import nullSource
from pcot.utils.html import HTML, Col


class TableIter:
    """Iterator over a Table"""

    def __init__(self, table):
        self.table = table
        self.iter = table.rows.__iter__()

    def __iter__(self):
        return self

    def __next__(self):  # note -this iterates over VALUES, not keys.
        row = self.table.rows[self.iter.__next__()]
        qq = [row[k] if k in row else self.table.NA for k in self.table.keys()]
        return qq


class Table:
    """Provides a way to construct tabular data on the fly, for output as a CSV.
    Create a new row with newRow(label) - if the label has already been used, an old row
    is selected to add more data or replace old data. Then add data with add(k,v).
    Once done, a table iterator will iterate over the rows fetching a list of entries. If
    one of the fields is not present for a row, the "NA item" will be used instead; by default
    it's a string 'NA'.
    """

    def __init__(self):
        self.rows = OrderedDict()
        self._keys = []
        self._currow = None
        self._internalLabelCt = 0  # used for when we don't give a label to newRow
        self.NA = 'NA'
        self.sigfigs = 5

    def getByIndices(self, args, sources):
        """Given a list of Datum index objects, return a Datum for the item in the row and column indicated.
        Row is first."""
        from pcot.datum import Datum
        from pcot.value import Value

        def get(d: Datum, c: OrderedDict, txt):
            if d.tp == Datum.NUMBER:
                if not d.val.isscalar():
                    raise ValueError("cannot use a vector as an index")
                k = int(d.val.n)
            elif d.tp == Datum.IDENT or d.tp == Datum.STRING:
                k = d.val
            else:
                raise ValueError(f"cannot use a {d.tp.name} as an index")
            # the key could be an integer or a string, but the dict keys are all strings
            if k not in c:
                k = str(k)
                if k not in c:
                    raise KeyError(f"key {k} not in the table {txt}")
            return c[k]

        row = get(args[0], self.rows, "rows")
        sd = None
        if len(args) > 1:
            # if a third argument is given, this is used to get stddeviation!
            # It's ignored if the value from the main column is not numeric
            v = get(args[1], row, "columns")
            if len(args) > 2:
                sd = get(args[2], row, "columns")
        else:
            # if there is no column given, assume there is only one
            k = next(iter(row.keys()))
            v = row[k]
        if isinstance(v, int) or isinstance(v, float) or isinstance(v, np.float32) or isinstance(v, np.float64):
            return Datum(Datum.NUMBER, Value(v, sd), sources)
        else:
            return Datum(Datum.STRING, str(v), sources)


    def newRow(self, label=None):
        """Select a new row or an existing row - the label is internal use only. For a new unique row
        without a label, leave it unset"""
        if label is None:
            # no label, autogenerate a new one that isn't in the dict
            while True:
                label = "internallab"+str(self._internalLabelCt)
                self._internalLabelCt += 1
                if label not in self.rows:
                    break

        if label in self.rows:
            self._currow = self.rows[label]
        else:
            self._currow = dict()
            self.rows[label] = self._currow

    def __len__(self):
        return len(self.rows)

    def add(self, k, v):
        if k not in self._keys:
            self._keys.append(k)
        self._currow[k] = v

    def keys(self):
        return self._keys

    def __iter__(self):
        return TableIter(self)

    def _printable(self, v):
        """Convert a value to a printable string. If it's a float, round it to the sigfigs"""
        if isinstance(v, float) or isinstance(v, np.float32):
            return round(v, self.sigfigs)
        else:
            return str(v).strip()

    def rowAsStrings(self, i):
        """Return row i as list of strings"""
        if i < 0 or i >= len(self.rows):
            raise IndexError("Row index out of range")
        return [self._printable(self.rows[self._keys[i]][k]) for k in self._keys]

    def __str__(self):
        """Convert entire table to a string"""
        s = io.StringIO()
        w = csv.writer(s,lineterminator='\n')
        w.writerow(self._keys)  # headers
        for r in self:
            r = [self._printable(v) for v in r]
            w.writerow(r)  # each row
        return s.getvalue()

    def htmlObj(self):
        """convert to html object"""
        # first generate the headers
#        headerRow = HTML("tr", [HTML("th", Col('red', k)) for k in self._keys])
        # note- removed colour, it was hard to read!
        headerRow = HTML("tr", [HTML("th", k) for k in self._keys])
        # now the rows
        rows = []
        for r in self:
            r = [self._printable(v) for v in r]
            rows.append(HTML("tr", [HTML("td", x) for x in r]))
        return HTML("table", headerRow, rows)

    def html(self):
        """convert to html string"""
        return self.htmlObj().string()

    def markdown(self):
        """convert to Markdown"""
        out = "|" + ("|".join(self._keys)) + "|\n"
        out += "|" + ("|".join(["-----" for _ in self._keys])) + "|\n"
        for r in self:
            r = [self._printable(v) for v in r]
            out += "|" + ("|".join(str(x) for x in r)) + "|\n"
        return out
    def text(self,titletext=None):
        """output as columns of text, each wide enough for its widest item"""
        # calculate column content widths
        colwidths = { k: len(k) for k in self._keys }
        for r in self:
            for k,v in zip(self._keys,r):
                colwidths[k] = max(colwidths[k],len(v))

        # total width of all cols (adding the number of cols because there's a gap between each)
        totalwidth = max(40,sum(colwidths.values())+len(colwidths)*3)

        # output a list of strings, justified to colwidths
        def colformat(lst):
            outs = [v.ljust(colwidths[k]) for k,v in zip(self._keys,lst)]
            return " | ".join(outs)

        # output header
        str = "="*totalwidth+"\n"
        if titletext is not None:
            titletext = "==="+titletext
            str = titletext+str[len(titletext):]
        str += colformat(self._keys)+"\n"
        str += "="*totalwidth+"\n"

        # and data
        for r in self:
            str += colformat(r)+"\n"
        return str
