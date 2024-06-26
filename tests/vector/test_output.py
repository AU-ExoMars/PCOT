from pcot import dq
from pcot.value import Value


def test_scalar_construct_and_output():
    """Test the output of a scalar value"""
    assert str(Value(10, 0.1)) == "10±0.1"
    assert str(Value(10, 0, dq.NOUNCERTAINTY)) == "10±0u"
    assert str(Value(10, 0.1, dq.NOUNCERTAINTY | dq.ERROR)) == "10±0.1uE"


def test_vector_construct_and_output():
    """Construct a vector and check the output"""

    # we can specify no unc and no dq
    v = Value([10, 20, 30])
    assert str(v) == "[10±0u, 20±0u, 30±0u]"

    # or no DQ
    v = Value([10, 20, 30], [0.1, 0.2, 0.3])
    assert str(v) == "[10±0.1, 20±0.2, 30±0.3]"

    # or provide DQ as a scalar
    v = Value([10, 20, 30], [0.1, 0.2, 0.3], dq.ERROR | dq.NOUNCERTAINTY)
    assert str(v) == "[10±0.1uE, 20±0.2uE, 30±0.3uE]"

    # no uncertainty, but an error
    v = Value([10, 20, 30], d=dq.ERROR)
    assert str(v) == "[10±0uE, 20±0uE, 30±0uE]"

    # or provide DQ as a vector
    v = Value([10, 20, 30], [0.1, 0.2, 0.3], [dq.ERROR, dq.TEST, dq.NONE])
    assert str(v) == "[10±0.1E, 20±0.2T, 30±0.3]"

    # we can also provide a scalar for unc
    v = Value([10, 20, 30], 0.1)
    assert str(v) == "[10±0.1, 20±0.1, 30±0.1]"

    # but not a scalar for N and a vector for unc
    try:
        v = Value(10, [0.1, 0.2, 0.3])
        assert False
    except ValueError:
        pass


def test_vector_output_trunc():
    """Test vector output truncation"""
    # if we create too big a vector, it should be truncated.
    # MAXARRAYDISPLAY is 10.
    v = Value([i for i in range(Value.MAXARRAYDISPLAY)])  # should not be truncated
    assert str(v) == "[0±0u, 1±0u, 2±0u, 3±0u, 4±0u, 5±0u, 6±0u, 7±0u, 8±0u, 9±0u]"

    # and now one too big
    v = Value([i for i in range(Value.MAXARRAYDISPLAY + 1)])    # should be truncated
    assert str(v) == "[0±0u, 1±0u, 2±0u, 3±0u, 4±0u, 5±0u, 6±0u, 7±0u, 8±0u, 9±0u...]"




