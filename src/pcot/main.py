# The main function with command line parsing, setting up the UI.
# Run from both __main__ and from the "pcot" entry point script.

import click

from pcot.subcommands.subcommands import cli


@cli.command("open", short_help="Run the PCOT application, loading any file specified")
@click.argument("file", required=False)
def open_cmd(file):
    """
    Run the PCOT application, loading any file specified. This is also the
    command run if `pcot` is given a bare filename, or no arguments at all,
    e.g. "pcot somefile.pcot" is equivalent to "pcot open somefile.pcot".
    """
    import pcot.app
    pcot.app.run(file)


def main():
    cli.main(prog_name="pcot")


if __name__ == "__main__":
    main()
