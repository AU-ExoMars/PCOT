from abc import ABC, abstractmethod
import filters


# a source for a channel - each channel in an image has a set of these, representing
# filename and filter.

class IChannelSource(ABC):
    @abstractmethod
    def getID(self):
        pass

    @abstractmethod
    def getFilterPos(self):
        pass

    @abstractmethod
    def getFilterName(self):
        pass

    @abstractmethod
    def getFilter(self):
        pass

    # this gets the string for a single source; you probably want stringForSet().

    @abstractmethod
    def string(self, capType):
        pass

    # get a string which is used for equality checking and hash generation,
    # it will (probably) never be seen by users.

    @abstractmethod
    def fullStr(self):
        pass

    #
    # end of abstract methods
    #
    #
    #

    def __str__(self):
        return self.getID() + "|" + self.getFilterPos()

    # pass a set of these objects to this method to get a string

    @classmethod
    def stringForSet(cls, s, capType):
        lst = [x.string(capType) for x in s]
        return "&".join(lst)

    # these objects are going to be in sets, so we need hash and equality operators.

    def __eq__(self, other):
        return self.fullStr() == other.fullStr()

    def __hash__(self):
            return hash(self.fullStr())


# used for channels which SHOULD have filters. The "pos"" will be
# a string giving the filter position, or just the name for ad-hoc
# channels (e.g. "red"). This is used for both real channels with
# real filter data, and RGB/grey channels (where band data is faked up).
# A flag indicates if the data is real or not, so nodes can check.

class ChannelSourceWithFilter(IChannelSource):
    def __init__(self, ident, filt, fake=True):
        self.id = ident  # identifying string for source, e.g. filename
        self.filter = filt
        self.fake = fake  # are these real filters or faked (e.g. just RGB)?

    def getID(self):
        return self.id

    def getFilterPos(self):
        return self.filter.position

    def getFilterName(self):
        return self.filter.name

    def getFilter(self):
        return self.filter

    def string(self, capType):   # implemented in sub
        pass

    def fullStr(self):  # implemented in sub
        pass


# create fake filter data for when we load in (say) RGB files.

def fakeFilter(name, cwl):
    return filters.Filter(cwl, 1, 1, position=name, name=name)


FAKEREDFILTER = fakeFilter("RED", 10000)
FAKEGREENFILTER = fakeFilter("GREEN", 90000)
FAKEBLUEFILTER = fakeFilter("BLUE", 8000)
FAKEBLACKFILTER = fakeFilter("BLACK", 100)
FAKEGREYFILTER = fakeFilter("GREY", 200)


## this is used for internal sources of individual RGB channels. Don't use the class,
# use the objects REDINTERNALSOURCE etc. Typically the images will be empty, and used
# to "pad out" merges.

class InternalChannelSource(ChannelSourceWithFilter):
    # pass in name and fake wavelength for sorting purposes in output, so that "red" channels are always assigned
    # to the red channel in an RGB image

    def __init__(self, name, filt):
        super().__init__("internal", filt, True)

    def string(self, capType):
        return self.getFilterPos()

    def fullStr(self):
        return "internal " + self.getFilterPos()


REDINTERNALSOURCE = InternalChannelSource("RED", FAKEREDFILTER)
GREENINTERNALSOURCE = InternalChannelSource("GREEN", FAKEGREENFILTER)
BLUEINTERNALSOURCE = InternalChannelSource("BLUE", FAKEBLUEFILTER)


## Used for RGB/Greyscale channels coming from "simple" images. Use the subclasses
# for r,g,b,grey.

class FileChannelSourceNoFilter(ChannelSourceWithFilter):
    def __init__(self, file, filt):
        super().__init__(file, filt, True)

    def fullStr(self):
        return self.getFilterPos() + "+++" + self.getID()

    def string(self, capType):
        if capType == 2:
            out = self.getID() + "|" + self.getFilterPos()
        else:
            out = self.getFilterPos()

        return out


class FileChannelSourceRed(FileChannelSourceNoFilter):
    def __init__(self, file):
        super().__init__(file, FAKEREDFILTER)


class FileChannelSourceGreen(FileChannelSourceNoFilter):
    def __init__(self, file):
        super().__init__(file, FAKEGREENFILTER)


class FileChannelSourceBlue(FileChannelSourceNoFilter):
    def __init__(self, file):
        super().__init__(file, FAKEBLUEFILTER)


## This is for channels in real, genuine PANCAM/AUPE images loaded from files.
class FileChannelSource(ChannelSourceWithFilter):

    # fpos could be None here if the regex is faulty, in which case we have no filter data.
    def __init__(self, file, fpos, aupe=False):
        if aupe:
            d = filters.AUPEfiltersByPosition
        else:
            d = filters.PANCAMfiltersByPosition
        if fpos in d:
            filt = d[fpos]
        else:
            filt = filters.DUMMY_FILTER
        super().__init__(file, filt, False)

    def fullStr(self):
        return self.getFilterPos() + "++" + self.getID()

    def string(self, capType):
        fname = self.getFilterName()
        fpos = self.getFilterPos()
        filt = self.getFilter()
        if capType == 0:  # filter position only
            return fpos
        elif capType == 1:  # filter position and name
            # show filter name and CWL
            return "{}/{}".format(fname, filt.cwl)
        elif capType == 2:  # file and filter pos
            # file and filter pos
            return self.getID() + "|" + fpos
        else:
            return fname
