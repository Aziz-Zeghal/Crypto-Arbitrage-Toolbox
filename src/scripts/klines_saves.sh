#!/bin/bash

set -e

# Run klines_save.py inside the "sandbox" conda environment
nohup conda run -n sandbox python klines_save.py > /dev/null 2>&1 &

# Print confirmation
echo "Script is running in the background with PID: $!"
