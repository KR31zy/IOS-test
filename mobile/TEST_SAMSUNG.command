#!/bin/bash
cd "$(dirname "$0")" || exit 1
if [ -d "$HOME/development/flutter/bin" ]; then export PATH="$HOME/development/flutter/bin:$PATH"; fi
python3 tools/test_usb.py "$@"
status=$?
printf '\nTest exited with status %s. Press Return to close.\n' "$status"
read -r _
exit "$status"
