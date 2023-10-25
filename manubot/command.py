"""
Manubot's command line interface
"""
import argparse
import logging
import pathlib
import sys
import warnings

import manubot
from manubot.util import import_function


def parse_arguments():
    """
    Read and process command line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Manubot: the manuscript bot for scholarly writing"
    )
    parser.add_argument(
        "--version", action="version", version=f"v{manubot.__version__}"
    )
    subparsers = parser.add_subparsers(
        title="subcommands", description="All operations are done through subcommands:"
    )
    # Require specifying a sub-command
    subparsers.required = True  # https://bugs.python.org/issue26510
    subparsers.dest = "subcommand"  # https://bugs.python.org/msg186387
    add_subparser_process(subparsers)
    add_subparser_cite(subparsers)
    add_subparser_webpage(subparsers)
    add_subparser_airevision(subparsers)
    add_subparser_aicite(subparsers)
    for subparser in subparsers.choices.values():
        subparser.add_argument(
            "--log-level",
            default="WARNING",
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            help="Set the logging level for stderr logging",
        )
    args = parser.parse_args()
    return args


def add_subparser_process(subparsers):
    parser = subparsers.add_parser(
        name="process",
        help="process manuscript content",
        description="Process manuscript content to create outputs for Pandoc consumption. "
        "Performs bibliographic processing and templating.",
    )
    parser.add_argument(
        "--content-directory",
        type=pathlib.Path,
        required=True,
        help="Directory where manuscript content files are located.",
    )
    parser.add_argument(
        "--output-directory",
        type=pathlib.Path,
        required=True,
        help="Directory to output files generated by this script.",
    )
    parser.add_argument(
        "--template-variables-path",
        action="append",
        default=[],
        help="Path or URL of a file containing template variables for jinja2. "
        "Serialization format is inferred from the file extension, with support for JSON, YAML, and TOML. "
        "If the format cannot be detected, the parser assumes JSON. "
        "Specify this argument multiple times to read multiple files. "
        "Variables can be applied to a namespace (i.e. stored under a dictionary key) "
        "like `--template-variables-path=namespace=path_or_url`. "
        "Namespaces must match the regex `[a-zA-Z_][a-zA-Z0-9_]*`.",
    )
    parser.add_argument(
        "--skip-citations",
        action="store_true",
        required=True,
        help="Skip citation and reference processing. "
        "Support for citation and reference processing has been moved from `manubot process` to the pandoc-manubot-cite filter. "
        "Therefore this argument is now required. "
        "If citation-tags.tsv is found in content, "
        "these tags will be inserted in the markdown output using the reference-link syntax for citekey aliases. "
        "Appends content/manual-references*.* paths to Pandoc's metadata.bibliography field.",
    )
    parser.add_argument(
        "--cache-directory",
        type=pathlib.Path,
        help="Custom cache directory. If not specified, caches to output-directory.",
    )
    parser.add_argument("--clear-requests-cache", action="store_true")
    parser.add_argument(
        "--skip-remote",
        action="store_true",
        help="Do not add the rootstock repository to the local git repository remotes.",
    )
    parser.set_defaults(function="manubot.process.process_command.cli_process")


def add_subparser_cite(subparsers):
    parser = subparsers.add_parser(
        name="cite",
        help="citekey to CSL JSON command line utility",
        description="Generate bibliographic metadata in CSL JSON format for one or more citation keys. "
        "Optionally, render metadata into formatted references using Pandoc. "
        "Text outputs are UTF-8 encoded.",
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        help="Specify a file to write output, otherwise default to stdout.",
    )
    format_group = parser.add_mutually_exclusive_group()
    format_group.add_argument(
        "--format",
        choices=["csljson", "cslyaml", "plain", "markdown", "docx", "html", "jats"],
        help="Format to use for output file. "
        "csljson and cslyaml output the CSL data. "
        "All other choices render the references using Pandoc. "
        "If not specified, attempt to infer this from the --output filename extension. "
        "Otherwise, default to csljson.",
    )
    format_group.add_argument(
        "--yml",
        dest="format",
        action="store_const",
        const="cslyaml",
        help="Short for --format=cslyaml.",
    )
    format_group.add_argument(
        "--txt",
        dest="format",
        action="store_const",
        const="plain",
        help="Short for --format=plain.",
    )
    format_group.add_argument(
        "--md",
        dest="format",
        action="store_const",
        const="markdown",
        help="Short for --format=markdown.",
    )
    parser.add_argument(
        "--csl",
        # redirects to the latest Manubot CSL Style.
        default="https://citation-style.manubot.org/",
        help="URL or path with CSL XML style used to style references "
        "(i.e. Pandoc's --csl option). "
        "Defaults to Manubot's style.",
    )
    parser.add_argument(
        "--bibliography",
        default=[],
        action="append",
        help="File to read manual reference metadata. "
        "Specify multiple times to load multiple files. "
        "Similar to pandoc --bibliography.",
    )
    parser.add_argument(
        "--no-infer-prefix",
        dest="infer_prefix",
        action="store_false",
        help="Do not attempt to infer the prefix for citekeys without a known prefix.",
    )
    parser.add_argument(
        "--allow-invalid-csl-data",
        dest="prune_csl",
        action="store_false",
        help="Allow CSL Items that do not conform to the JSON Schema. Skips CSL pruning.",
    )
    parser.add_argument(
        "citekeys",
        nargs="+",
        help="One or more (space separated) citation keys to generate bibliographic metadata for.",
    )
    parser.set_defaults(function="manubot.cite.cite_command.cli_cite")


def add_subparser_webpage(subparsers):
    parser = subparsers.add_parser(
        name="webpage",
        help="deploy Manubot outputs to a webpage directory tree",
        description="Update the webpage directory tree with Manubot output files. "
        "This command should be run from the root directory of a Manubot manuscript that follows the Rootstock layout, containing `output` and `webpage` directories. "
        "HTML and PDF outputs are copied to the webpage directory, which is structured as static source files for website hosting.",
    )
    parser.add_argument(
        "--checkout",
        nargs="?",
        const="gh-pages",
        default=None,
        help="branch to checkout /v directory contents from. "
        "For example, --checkout=upstream/gh-pages. "
        "--checkout is equivalent to --checkout=gh-pages. "
        "If --checkout is ommitted, no checkout is performed.",
    )
    parser.add_argument(
        "--version",
        help="Used to create webpage/v/{version} directory. "
        "Generally a commit hash, tag, or 'local'. "
        "When omitted, version defaults to the commit hash on CI builds and 'local' elsewhere.",
    )
    parser.add_argument(
        "--timestamp",
        action="store_true",
        help="timestamp versioned manuscripts in webpage/v using OpenTimestamps. "
        "Specify this flag to create timestamps for the current HTML and PDF outputs and upgrade any timestamps from past manuscript versions.",
    )
    cache_group = parser.add_mutually_exclusive_group()
    cache_group.add_argument(
        "--no-ots-cache", action="store_true", help="disable the timestamp cache."
    )
    cache_group.add_argument(
        "--ots-cache",
        default=pathlib.Path("ci/cache/ots"),
        type=pathlib.Path,
        help="location for the timestamp cache (default: ci/cache/ots).",
    )
    parser.set_defaults(function="manubot.webpage.webpage_command.cli_webpage")


def add_subparser_airevision(subparsers):
    parser = subparsers.add_parser(
        name="ai-revision",
        help="revise manuscript content with language models",
        description="Revise manuscript content using AI models to suggest text improvements.",
    )
    parser.add_argument(
        "--content-directory",
        type=pathlib.Path,
        required=True,
        help="Directory where manuscript content files are located.",
    )
    parser.add_argument(
        "--model-type",
        type=str,
        required=False,
        default="GPT3CompletionModel",
        help="Model type used to revise the manuscript. Default is GPT3CompletionModel. "
        "It can be any subclass of manubot_ai_editor.models.ManuscriptRevisionModel",
    )
    parser.add_argument(
        "--model-kwargs",
        required=False,
        metavar="key=value",
        nargs="+",
        help="Keyword arguments for the revision model (--model-type), with format key=value.",
    )
    parser.set_defaults(function="manubot.ai_revision.ai_revision_command.cli_process")

def add_subparser_aicite(subparsers):
    parser = subparsers.add_parser(
        name="ai-cite",
        help="revise manuscript content with suggested citations",
        description="Revise manuscript content using AI models to suggest citations.",
    )
    parser.add_argument(
        "--content-directory",
        type=pathlib.Path,
        required=True,
        help="Directory where manuscript content files are located.",
    )
    parser.add_argument(
        "--model-type",
        type=str,
        required=False,
        default="GPT3CompletionModel",
        help="Model type used to revise the manuscript. Default is GPT3CompletionModel. "
        "It can be any subclass of manubot_ai_cite.models.ManuscriptRevisionModel",
    )
    parser.add_argument(
        "--model-kwargs",
        required=False,
        metavar="key=value",
        nargs="+",
        help="Keyword arguments for the revision model (--model-type), with format key=value.",
    )
    parser.set_defaults(function="manubot.ai_cite.ai_cite_command.cli_process")


def setup_logging_and_errors() -> dict:
    """
    Configure warnings and logging.
    Set up an ErrorHandler to detect whether messages have been logged
    at or above the ERROR level.
    """
    import errorhandler

    # Track if message gets logged with severity of error or greater
    # See https://stackoverflow.com/a/45446664/4651668
    error_handler = errorhandler.ErrorHandler()

    # Log DeprecationWarnings
    warnings.simplefilter("always", DeprecationWarning)
    logging.captureWarnings(True)

    # Log to stderr
    logger = logging.getLogger()
    stream_handler = logging.StreamHandler(stream=sys.stderr)
    stream_handler.setFormatter(
        logging.Formatter("## {levelname}\n{message}", style="{")
    )
    logger.addHandler(stream_handler)
    return {
        "logger": logger,
        "error_handler": error_handler,
    }


def exit_if_error_handler_fired(error_handler):
    """
    If a message has been logged with severity of ERROR or greater,
    exit Python with a nonzero code.
    """
    if error_handler.fired:
        logging.critical("Failure: exiting with code 1 due to logged errors")
        raise SystemExit(1)


def main():
    """
    Called as a console_scripts entry point in setup.cfg. This function defines
    the manubot command line script.
    """
    diagnostics = setup_logging_and_errors()
    args = parse_arguments()
    diagnostics["logger"].setLevel(getattr(logging, args.log_level))
    function = import_function(args.function)
    function(args)
    exit_if_error_handler_fired(diagnostics["error_handler"])
