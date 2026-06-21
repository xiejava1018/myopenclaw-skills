"""Unified CLI entry point: build / check."""
import argparse
import json
import sys

import export


def cmd_check(_args) -> int:
    status = export.check_status()
    print(json.dumps(status, indent=2, ensure_ascii=False))
    if not status["available"]:
        print(status["install_hint"], file=sys.stderr)
        return 1
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="drawio-diagram")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="verify draw.io CLI is available")
    args = parser.parse_args(argv)
    if args.command == "check":
        return cmd_check(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
