#!/bin/bash
# This script should run on your local machine to sync trades to cloud
# Usage: ./sync_trades.sh

REMOTE_USER="your_user"
REMOTE_HOST="your_server_ip"
REMOTE_PATH="/var/www/html/dashboard"

while true; do
    scp trade_history.json $REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/
    sleep 30
done
