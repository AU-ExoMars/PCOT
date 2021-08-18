"""
Assorted geometry
"""

from typing import Tuple, Optional


def rectIntersection(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> \
        Optional[Tuple[int, int, int, int]]:
    """Given two rectangles as (x,y,w,h) tuples, find the intersection. Returns
    None if they do not intersect."""
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2 = ax1 + aw
    ay2 = ay1 + ah
    bx2 = bx1 + bw
    by2 = by1 + bh

    x1 = max(min(ax1, ax2), min(bx1, bx2))
    y1 = max(min(ay1, ay2), min(by1, by2))
    x2 = min(max(ax1, ax2), max(bx1, bx2))
    y2 = min(max(ay1, ay2), max(by1, by2))
    if x1 < x2 and y1 < y2:
        return x1, y1, x2 - x1, y2 - y1

