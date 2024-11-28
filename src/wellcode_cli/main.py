import logging

import rich_click as click
from rich.console import Console

from wellcode_cli import __version__

from .commands import chat, chat_interface, completion, config, report, review

# Configure rich-click
click.USE_RICH_MARKUP = True
click.USE_MARKDOWN = True
click.SHOW_ARGUMENTS = True
click.GROUP_ARGUMENTS_OPTIONS = True
click.STYLE_ERRORS_SUGGESTION = "yellow italic"
click.ERRORS_SUGGESTION = "Try '--help' for more information."

# Initialize rich console
console = Console()


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="wellcode-cli")
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Increase verbosity (can be used multiple times)",
)
@click.pass_context
def cli(ctx, verbose):
    """🚀 Wellcode CLI - Engineering Metrics Analysis Tool"""
    # Set up logging based on verbosity level
    if verbose == 0:
        log_level = logging.WARNING
    elif verbose == 1:
        log_level = logging.INFO
    else:  # verbose >= 2
        log_level = logging.DEBUG

    logging.basicConfig(level=log_level, format="%(levelname)s:%(message)s")

    if ctx.invoked_subcommand is None:
        # Start interactive mode by default
        ctx.invoke(chat_interface)


# Add commands to CLI group
cli.add_command(review)
cli.add_command(config)
cli.add_command(chat_interface, name="chat")
cli.add_command(chat)
cli.add_command(report)
cli.add_command(completion)


def main():
    cli()


if __name__ == "__main__":
    main()
