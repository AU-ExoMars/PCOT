from pcot.utils.geom import Rect


def test_rect_ctor():
    rr = Rect(10, 20, 30, 40)
    x, y, w, h = rr
    assert x == 10
    assert y == 20
    assert w == 30
    assert h == 40


def test_rect_intersect1():
    a = Rect(10, 20, 30, 40)
    b = Rect(0, 0, 100, 100)
    assert a == a.intersection(b)
    assert a == b.intersection(a)


def test_rect_intersect2():
    a = Rect(13, 23, 4, 3)
    b = Rect(14, 24, 5, 4)
    assert a.intersection(b) == Rect(14, 24, 3, 2)
    assert b.intersection(a) == Rect(14, 24, 3, 2)


def test_rect_intersect3():
    a = Rect(13, 23, 4, 3)
    b = Rect(12, 24, 7, 3)
    assert a.intersection(b) == Rect(13, 24, 4, 2)


def test_rect_intersect4():
    a = Rect(13, 23, 4, 3)
    b = Rect(14, 21, 2, 4)
    assert a.intersection(b) == Rect(14, 23, 2, 2)


def test_rect_corners():
    a = Rect(13, 23, 100, 300)
    x1, y1, x2, y2 = a.corners()
    assert x1 == 13
    assert y1 == 23
    assert x2 == 113
    assert y2 == 323
