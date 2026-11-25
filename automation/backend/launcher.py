"""Open the local HIL frontend in a desktop webview."""
import argparse
import sys

from .app import run_desktop


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        import webview
    except ImportError:
        print('Install GUI dependencies: python -m pip install -e ".[gui]"', file=sys.stderr)
        return 1
    run_desktop(webview)
    return 0


if __name__ == "__main__":
    sys.exit(main())
