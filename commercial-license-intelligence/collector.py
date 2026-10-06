"""
Root convenience CLI wrapper for running Windows Endpoint Application Discovery.
"""

import sys
import os

root_dir = os.path.dirname(os.path.abspath(__file__))
agent_dir = os.path.join(root_dir, "endpoint-agent")

for p in [root_dir, agent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from windows.collector import main

if __name__ == "__main__":
    main()
