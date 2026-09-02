"""
This is the subcommand processing system, built on top of Click.

It preserves the calling convention of the previous hand-rolled, argparse-based
system (originally adapted from Adrian Sampson's "beets"): subcommand modules
call `subcommand([...])` with a list of `argument(...)` specs and a short
description, decorating a function that takes a single `args` namespace object
(so `gencam.py`, `genrefl.py` etc. did not need to change at all).

It also preserves the "dual dispatch" behaviour of `pcot`: if the first
non-option token on the command line is a recognised subcommand name, that
subcommand runs; otherwise the fallback command (registered via
`maincommand()`) runs, so `pcot somefile.pcot` still opens the GUI.
"""

import argparse
import logging

import click

logger = logging.getLogger(__name__)

# name -> click.Command, kept for parity with the old system and for introspection.
subcommands = {}

# The name under which the "main command" (the GUI, opened via maincommand())
# is registered as an ordinary click subcommand, so that dispatch can fall
# back to it.
FALLBACK_COMMAND_NAME = "open"


class PCOTArgument(click.Argument):
    """
    A click Argument that still brackets its metavar as "[OPTIONAL]" in the
    usage line when it's not required, even though a custom metavar was
    given - click's own make_metavar() only does this when it computes the
    metavar itself (see click.Argument.make_metavar), so a plain
    click.Argument with an explicit `metavar=` loses that visual cue.
    """

    def make_metavar(self, ctx):
        var = super().make_metavar(ctx)
        if self.metavar is not None and not self.required and not var.startswith("["):
            var = f"[{var}]"
        return var


class PCOTCommand(click.Command):
    """
    A click Command that also remembers help text for its positional arguments.
    Click's Argument (unlike Option) has no `help` text of its own - only a
    metavar in the usage line - so we keep the descriptions supplied via
    `argument()` on the side and render them as an "Arguments" section, the
    way the old argparse-based help did.
    """

    def __init__(self, *args, arg_help=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.arg_help = arg_help or []

    def format_options(self, ctx, formatter):
        if self.arg_help:
            with formatter.section("Arguments"):
                formatter.write_dl(self.arg_help)
        super().format_options(ctx, formatter)


def argument(*name_or_flags, **kwargs):
    """
    Convenience function to properly format arguments to pass to the
    subcommand decorator - same calling convention as the old argparse-based
    system: `argument('name', ...)` for a positional, `argument('--flag', '-f',
    ...)` for an option, with argparse-style kwargs (type, metavar, help,
    nargs, action, choices, dest, default, const).
    """
    return list(name_or_flags), dict(kwargs)


def _is_option(name_or_flags):
    return any(f.startswith('-') for f in name_or_flags)


def _build_param(name_or_flags, kwargs):
    """Translate one argument() spec into a click Parameter, plus an optional
    (metavar, help) pair for PCOTCommand's "Arguments" section if it's a
    positional with help text."""
    kwargs = dict(kwargs)
    help_text = kwargs.pop('help', None)
    metavar = kwargs.get('metavar')
    dest = kwargs.pop('dest', None)
    action = kwargs.pop('action', None)
    nargs = kwargs.pop('nargs', None)
    choices = kwargs.pop('choices', None)
    const = kwargs.pop('const', None)

    if choices is not None:
        kwargs['type'] = click.Choice(choices)

    if _is_option(name_or_flags):
        # options can share a single "dest" across several argument() calls
        # (e.g. --debug/-d and --verbose/-v both feeding "loglevel"); click
        # does this by including the bare parameter name in the declarations,
        # the same trick argparse's `dest` performs.
        decls = list(name_or_flags)
        if dest:
            decls = decls + [dest]
        if action == 'store_true':
            kwargs['is_flag'] = True
        elif action == 'store_const':
            kwargs.setdefault('is_flag', True)
            kwargs['flag_value'] = const
        if help_text is not None:
            kwargs['help'] = help_text
        return click.Option(decls, **kwargs), None
    else:
        decls = list(name_or_flags)
        if nargs == '*':
            kwargs['nargs'] = -1
            kwargs.setdefault('required', False)
        elif nargs == '?':
            kwargs.setdefault('required', False)
        else:
            kwargs.setdefault('required', True)
        param = PCOTArgument(decls, **kwargs)
        label = metavar or param.human_readable_name.upper()
        arg_help_entry = (label, help_text) if help_text else None
        return param, arg_help_entry


def _short_help(doc):
    return (doc or "").strip().splitlines()[0] if doc else ""


def _make_callback(func):
    def callback(**kwargs):
        # click gives nargs=-1/'*' arguments back as tuples; the old system
        # (and the subcommand bodies) expect a list, as argparse produced.
        ns = argparse.Namespace(**{k: (list(v) if isinstance(v, tuple) else v)
                                    for k, v in kwargs.items()})
        func(ns)
    return callback


# The top-level command group. Subcommands are registered into this via
# subcommand()/maincommand(); common (global) options are added via
# set_common_args(). Its callback is assigned by whoever calls
# set_common_args()'s caller (main.py) once all the shared options are known.
cli = click.Group(name="pcot", invoke_without_command=True)


def subcommand(args=None, shortdesc="", parent=None):
    """
    Decorator to define a new subcommand. `args` is a list of argument()
    specs, `shortdesc` is shown in the top-level command listing.
    """
    group = parent or cli

    def decorator(func):
        params = []
        arg_help = []
        for name_or_flags, kwargs in (args or []):
            param, entry = _build_param(name_or_flags, kwargs)
            params.append(param)
            if entry:
                arg_help.append(entry)

        cmd = PCOTCommand(name=func.__name__, params=params, callback=_make_callback(func),
                           help=func.__doc__, short_help=shortdesc, arg_help=arg_help)
        group.add_command(cmd)
        subcommands[func.__name__] = cmd
        return func

    return decorator


def maincommand(args=None):
    """
    Decorator for the "main command" - what runs when no recognised
    subcommand name is given on the command line (e.g. `pcot somefile.pcot`).
    Registered as an ordinary subcommand under FALLBACK_COMMAND_NAME so that
    the dispatch wrapper in main.py can invoke it by name.
    """

    def decorator(func):
        params = []
        arg_help = []
        for name_or_flags, kwargs in (args or []):
            param, entry = _build_param(name_or_flags, kwargs)
            params.append(param)
            if entry:
                arg_help.append(entry)

        cmd = PCOTCommand(name=FALLBACK_COMMAND_NAME, params=params, callback=_make_callback(func),
                           help=func.__doc__, short_help=_short_help(func.__doc__))
        cli.add_command(cmd)
        subcommands[FALLBACK_COMMAND_NAME] = cmd
        return func

    return decorator


def set_common_args(args):
    """
    Add options common to every subcommand (and the main command) - things
    like --debug/-v/--log-level. These must be given before the subcommand
    name on the command line, e.g. `pcot -d gencam ...`.
    """
    for name_or_flags, kwargs in args:
        param, _ = _build_param(name_or_flags, kwargs)
        cli.params.append(param)


def peek_remainder(argv):
    """
    Leniently parse just the common (group-level) options out of argv,
    returning whatever's left over - mirrors argparse's parse_known_args, and
    is used by main.py to work out whether the next token is a recognised
    subcommand name, or should fall back to the main command.
    """
    peek_cmd = click.Command(name=cli.name, params=list(cli.params),
                              context_settings={"ignore_unknown_options": True, "allow_extra_args": True})
    ctx = peek_cmd.make_context(cli.name, list(argv), resilient_parsing=True)
    return ctx.args
