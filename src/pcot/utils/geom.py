"""
Assorted geometry
"""

from typing import Tuple, Optional


class Rect:
    vars = ('x', 'y', 'w', 'h')  # see __getitem__

    def __init__(self, x, y, w, h):
        self.x = x
        self.y = y
        self.w = w
        self.h = h

    def __contains__(self, xyTuple):
        x, y = xyTuple
        return self.x <= x < self.x + self.w and self.y <= y < self.y + self.h

    def copy(self):
        return Rect(self.x, self.y, self.w, self.h)

    def __str__(self):
        return "Rect-{}-{}-{}x{}".format(self.x, self.y, self.w, self.h)

    def __repr__(self):
        return "Rect-{}-{}-{}x{}".format(self.x, self.y, self.w, self.h)

    def corners(self):
        return self.x, self.y, self.x + self.w, self.y + self.h

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y and self.w == other.w and self.h == other.h

    def __getitem__(self, item):
        """This is here so we can iterate over the object, so we can do x,y,w,h = rect for
        legacy code"""
        if item < 4:
            return self.__dict__[Rect.vars[item]]
        else:
            raise IndexError()

    def size(self):
        """return how many pixels are in the ROI bounding box"""
        return self.w*self.h


    def intersection(self, other: 'Rect') -> Optional['Rect']:
        """Given two rectangles find the intersection. Returns
        None if they do not intersect."""
        ax1, ay1, aw, ah = self  # can do this because can iterate!
        bx1, by1, bw, bh = other
        ax2 = ax1 + aw
        ay2 = ay1 + ah
        bx2 = bx1 + bw
        by2 = by1 + bh

        x1 = max(min(ax1, ax2), min(bx1, bx2))
        y1 = max(min(ay1, ay2), min(by1, by2))
        x2 = min(max(ax1, ax2), max(bx1, bx2))
        y2 = min(max(ay1, ay2), max(by1, by2))
        if x1 < x2 and y1 < y2:
            return Rect(x1, y1, x2 - x1, y2 - y1)
        else:
            return None

    def astuple(self):
        return self.x, self.y, self.w, self.h

    @staticmethod
    def fromtuple(t):
        if t is None:
            return None
        else:
            return Rect(*t)
