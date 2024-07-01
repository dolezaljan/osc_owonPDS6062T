#!/usr/bin/env python3
import os
import sys
import argparse

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from relay_srv import DEFAULT_PORT, WS_TYPES
DEFAULT_HOST="localhost"

class OsciCommander():
    def __init__(self, host, port, silent = True):
        self.host = host
        self.port = port
        self.silent = silent

    def query(self, query: str, silent = None):
        r = requests.post(f'http://{self.host}:{self.port}/query', data=query)
        s = self.silent if silent is None else silent
        None if s else print(r.content)
        return r

    def write(self, cmd: str):
        r = requests.post(f'http://{self.host}:{self.port}/write', data=cmd)
        return r

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start interactive session allowing to command and query oscilloscope.")
    parser.add_argument(
        "-t",
        "--host",
        help="Host of the oscilloscope relay.",
        type=str,
        nargs='?',
        default=DEFAULT_HOST,
    )
    parser.add_argument(
        "-p",
        "--port",
        help="Port of the oscilloscope relay.",
        type=int,
        nargs='?',
        default=DEFAULT_PORT,
    )
    return parser

if __name__ == "__main__":
    parser = build_parser()
    pargs = parser.parse_args(sys.argv[1:])

    c = OsciCommander(pargs.host, pargs.port, False)

    import code, rlcompleter, readline
    history_file_path=os.path.expanduser('~/.python_history')
    if os.path.exists(history_file_path):
        readline.read_history_file(history_file_path)
    readline.parse_and_bind("tab: complete")
    print(" - c.query('*IDN?')")
    print(" - c.write(':HORIzontal:SCALe 100ms')")
    print("")
    code.interact(local=locals())
