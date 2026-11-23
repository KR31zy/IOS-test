#!/bin/bash
cd "$(dirname "$0")" || exit 1
printf 'Start the isolated test server? This does not use existing farm data.\nType LAN to allow a debug phone on your trusted Wi-Fi, or press Return for this computer only: '
read -r choice
if [ "$choice" = LAN ]; then python3 tools/start_test_server.py --lan; else python3 tools/start_test_server.py; fi
