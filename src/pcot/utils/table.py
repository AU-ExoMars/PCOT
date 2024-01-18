import csv
import io
from collections import OrderedDict

import numpy as np

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

    def __str__(self):
        """Convert entire table to a string"""
        s = io.StringIO()
        w = csv.writer(s)
        w.writerow(self._keys)  # headers
        for r in self:
            r = [self._printable(v) for v in r]
            w.writerow(r)  # each row
        return s.getvalue()

    def htmlObj(self):
        """convert to html object"""
        # first generate the headers
        headerRow = HTML("tr", [HTML("th", Col('red', k)) for k in self._keys])
        # now the rows
        rows = []
        for r in self:
            r = [self._printable(v) for v in r]
            rows.append(HTML("tr", [HTML("td", x) for x in r]))
        return HTML("table", headerRow, rows)

    def html(self):
        """convert to html string"""
        return self.htmlObj().run()

    def markdown(self):
        """convert to Markdown"""
        out = "|" + ("|".join(self._keys)) + "|\n"
        out += "|" + ("|".join(["-----" for _ in self._keys])) + "|\n"
        for r in self:
            r = [self._printable(v) for v in r]
            out += "|" + ("|".join(x for x in r)) + "|\n"
        return out