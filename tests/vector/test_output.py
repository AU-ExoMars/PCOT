from pcot import dq
from pcot.value import Value


def test_scalar_output():
    """Test the output of a scalar value"""
    assert str(Value(10, 0.1)) == "10±0.1"
    assert str(Value(10, 0, dq.NOUNCERTAINTY)) == "10±0u"
    assert str(Value(10, 0.1, dq.NOUNCERTAINTY | dq.ERROR)) == "10±0.1uE"


def test_vector_output():
    """Construct a vector and check the output"""

    # we can specify no unc and no dq
    v = Value([10, 20, 30])
    assert str(v) == "[10±0, 20±0, 30±0]"

    # or no DQ
    v = Value([10, 20, 30], [0.1, 0.2, 0.3])
    assert str(v) == "[10±0.1, 20±0.2, 30±0.3]"

    # or provide DQ as a scalar
    v = Value([10, 20, 30], [0.1, 0.2, 0.3], dq.ERROR | dq.NOUNCERTAINTY)
    assert str(v) == "[10±0.1uE, 20±0.2uE, 30±0.3uE]"

    # or provide DQ as a vector
    v = Value([10, 20, 30], [0.1, 0.2, 0.3], [dq.ERROR, dq.NOUNCERTAINTY, dq.NONE])
    assert str(v) == "[10±0.1E, 20±0.2u, 30±0.3]"

    # we can also provide a scalar for unc
    v = Value([10, 20, 30], 0.1)
    assert str(v) == "[10±0.1, 20±0.1, 30±0.1]"

    # but not a scalar for N and a vector for unc
    try:
        v = Value(10, [0.1, 0.2, 0.3])
        assert False
    except ValueError:
        pass
