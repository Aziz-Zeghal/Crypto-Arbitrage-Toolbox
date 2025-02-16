#!/bin/bash

set -e

source activate base
conda activate sandbox

nohup python klines_save.py > /dev/null 2>&1 &

# Print confirmation
echo "Script is running in the background with PID: $!"
