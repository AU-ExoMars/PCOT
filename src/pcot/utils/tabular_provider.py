"""
Abstract data class for tabular data providers. These convert certain data
(e.g. SpectrumSetData) into tabular data which can be shown in a TabularDataWidget.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional

from pcot.parameters.taggedaggregates import TaggedDict


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
