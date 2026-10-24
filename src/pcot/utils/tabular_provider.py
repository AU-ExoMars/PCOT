"""
Abstract data class for tabular data providers. These convert certain data
(e.g. SpectrumSetData) into tabular data which can be shown in a TabularDataWidget.
"""
import csv
import io
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, TextIO

from pcot.parameters.taggedaggregates import TaggedDict


def naturalSortKey(s: str):
    """Sort key which compares runs of digits as numbers, so "2" comes before "10" and "img2" before
    "img10". Case is ignored, except to break ties. Use this to sort row names in tabular output."""
    # splitting on a capturing group alternates text and digit runs, always starting with text,
    # so items at the same position are always the same type and compare safely.
    parts = re.split(r'(\d+)', s)
    return [int(p) if i % 2 else p.casefold() for i, p in enumerate(parts)], s


class TabularIterator(ABC):
    """Every iterator created by a TabularDataProvider must implement this"""
    def __iter__(self):
        return self

    @abstractmethod
    def __next__(self) -> Dict[str, str]:
        """Return the next row as a dict of column name to value"""
        pass


class TabularProvider(ABC):
    """
    Provides a tabular view for some kind of data.
    """
    @abstractmethod
    def getParams(self) -> Optional[TaggedDict]:
        """Return a reference to the parameters for this provider for use or
        modification, or None for no parameters (the provider is not configurable)"""
        pass

    @abstractmethod
    def getHeaders(self) -> List[str]:
        """Return the column headers for the table"""
        pass

    @abstractmethod
    def __iter__(self) -> TabularIterator:
        """The provider must be iterable, and the iterator must be a TabularIterator"""
        pass


    def writeCSV(self, f: TextIO):
        """Write the provider's table as CSV to a text file object, which should be opened with newline=''
        so that line endings aren't translated. Lines end in '\n' on all platforms."""
        w = csv.writer(f, lineterminator='\n')
        headers = self.getHeaders()
        w.writerow(headers)
        for row in self:
            w.writerow([row[k] for k in headers])


    def csvString(self) -> str:
        """Return the provider's table as a CSV string"""
        s = io.StringIO()
        self.writeCSV(s)
        return s.getvalue()
