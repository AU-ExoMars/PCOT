import click

from pcot.subcommands.subcommands import cli


@cli.command(short_help="Run a graph using a PCOT batch (parameter) file")
@click.argument("doc")
@click.argument("file")
@click.argument("vars", nargs=-1)
def batch(doc, file, vars):
    """
    Run a PCOT batch (parameter) file.

    DOC is the document containing the graph, FILE is the batch file to run, and the optional VARS are
    variables to set in the batch file (vars[0], vars[1], ...).
    """
    import jinja2
    from pathlib import Path

    import pcot
    from pcot.parameters.runner import Runner

    pcot.setup()
    jinja_env = jinja2.Environment()
    jinja_env.globals['vars'] = list(vars)

    runner = Runner(Path(doc), jinja_env)
    runner.run(Path(file))
