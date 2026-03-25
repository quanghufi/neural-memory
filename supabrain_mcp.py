"""
SupaBrain MCP Server — Neural Memory on Supabase.
Wrapper that registers PostgreSQLStorage plugin, then starts nmem-mcp.
"""
import os
import sys
import logging

# Silence all logging to stderr (MCP uses stdio, stderr output can cause EOF)
logging.disable(logging.CRITICAL)

# Set Supabase connection
os.environ["DATABASE_URL"] = (
    "postgresql://postgres.ndnzdahhvolftrclunlc:"
    "aQ%40%40020319%40%40@"
    "aws-1-ap-southeast-1.pooler.supabase.com:5432/"
    "postgres?sslmode=require"
)
os.environ["NM_MODE"] = "postgres"

# Add project dir for supabrain_plugin
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Register plugin (silenced)
try:
    import supabrain_plugin
except Exception:
    pass

# Start MCP server
from neural_memory.mcp.server import main
main()
