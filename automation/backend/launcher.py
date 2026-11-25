"""Open the local HIL frontend in a desktop webview."""
import argparse
import sys

from .app import run_desktop


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true",
                        help="Open the frontend with sample devices and no hardware API")
    args = parser.parse_args(argv)
    try:
        import webview
    except ImportError:
        print('Install GUI dependencies: python -m pip install -e ".[gui]"', file=sys.stderr)
        return 1
    run_desktop(webview, demo=args.demo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
