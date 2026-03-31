#!/bin/bash
# Start the Configuration UI

echo "🚀 Starting Broken Link Checker Configuration UI..."
echo ""

# Install Flask if needed
pip3 install flask >/dev/null 2>&1

# Start the UI
python3 config_ui.py
