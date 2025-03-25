from pcot.subcommands import subcommand,argument

@subcommand(
    [argument("doc", metavar="DOC", help="The document containing the graph"),
     argument("file", metavar="FILE", help="The batch file to run"),
     argument('vars', nargs='*', help='variables to set in the batch file (vars[0], vars[1], ...)')],
    shortdesc="Run a graph using a PCOT batch (parameter) file"
)
def batch(args):
    """
    Run a PCOT batch (parameter) file.
    """
    import jinja2
    from pathlib import Path

    import pcot
    from pcot.parameters.runner import Runner

    pcot.setup()
    jinja_env = jinja2.Environment()
    jinja_env.globals['vars'] = args.vars

    runner = Runner(Path(args.doc), jinja_env)
    runner.run(Path(args.file))
