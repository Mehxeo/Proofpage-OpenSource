"""Console transport for AI clients; stdout is reserved for JSON-RPC."""
import sys
if '--extract-worker' in sys.argv:
    from proofpage.media_worker import main
    main()
    raise SystemExit(0)

import argparse
from proofpage.core import Store
from proofpage.mcp import run

parser = argparse.ArgumentParser(description='Proofpage local MCP server')
parser.add_argument('--home', required=True)
args = parser.parse_args()
run(Store(args.home))
