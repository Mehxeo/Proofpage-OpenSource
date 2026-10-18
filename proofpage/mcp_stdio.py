"""Absolute-path entry point for clients that do not support a cwd setting."""
import argparse
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from proofpage.core import Store
from proofpage.mcp import run


def main():
    parser = argparse.ArgumentParser(description='Proofpage local MCP server')
    parser.add_argument('--home', required=True)
    args = parser.parse_args()
    run(Store(args.home))


if __name__ == '__main__':
    main()
