import pcot
from pcot.datum import Datum
from pcot.parameters.runner import Runner
from fixtures import globaldatadir

def test_create_runner(globaldatadir):
    pcot.setup()
    r = Runner(globaldatadir / "doubler.pcot")


def test_run_noparams(globaldatadir):
    pcot.setup()
    r = Runner(globaldatadir / "doubler.pcot")
    r.run(None)


def test_run_with_input(globaldatadir):
    pcot.setup()
    r = Runner(globaldatadir / "doubler.pcot")

    test = f"""
    inputs.0.rgb.filename = {globaldatadir/'basn2c16.png'}  # colour image
    """
    r.run(None, test)

