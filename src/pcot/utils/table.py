import csv
import io
from collections import OrderedDict


class TableIter:
    """Iterator over a Table"""

    def __init__(self, table):
        self.table = table
        self.iter = table._rows.__iter__()

    def __iter__(self):
        return self

    def __next__(self):  # note -this iterates over VALUES, not keys.
        row = self.table._rows[self.iter.__next__()]
        qq = [row[k] if k in row else self.table.NA for k in self.table.keys()]
        return qq


class Table:
    """Provides a way to construct tabular data on the fly, for output as a CSV.
    Create a new row with newRow(label) - if the label has already been used, an old row
    is selected to add more data. Then add data with add(k,v).
    Once done, a table iterator will iterate over the rows fetching a list of entries. If
    one of the fields is not present for a row, the "NA item" will be used instead; by default
    it's a string 'NA'.
    """

    def __init__(self):
        self._keys = []
        self._rows = OrderedDict()
        self._currow = None
        self.NA = 'NA'
        self.sigfigs = 5

    def newRow(self, label):
        if label in self._rows:
            self._currow = self._rows[label]
        else:
            self._currow = dict()
            self._rows[label] = self._currow

    def add(self, k, v):
        if k not in self._keys:
            self._keys.append(k)
        self._currow[k] = v

    def keys(self):
        return self._keys

    def __iter__(self):
        return TableIter(self)

    def __str__(self):
        """Convert entire table to a string"""
        s = io.StringIO()
        w = csv.writer(s)
        w.writerow(self._keys)  # headers
        for r in self:
            r = [round(v, self.sigfigs) if isinstance(v, float) else v for v in r]
            w.writerow(r)  # each row
        return s.getvalue()
