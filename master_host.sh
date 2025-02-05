#!/bin/bash
# master_host.sh
# A master script to launch the host-side components:
#   - Central Log Server
#   - Signaling Server
#   - Receiver
#
# Note: The sender should be launched on the remote machine.

# Preconfigure CENTRAL_LOG_IP if not already set.
if [ -z "$CENTRAL_LOG_IP" ]; then
    if [ -f "$HOME/.central_log_config" ]; then
        export CENTRAL_LOG_IP=$(cat "$HOME/.central_log_config")
    else
        echo "CENTRAL_LOG_IP is not set. Please configure centralized logging now."
        # Run an interactive Python command to trigger the prompt.
        python3 -c "import log_config; log_config.configure_logging('master_setup')" || {
            echo "Configuration failed. Defaulting to 127.0.0.1"
            export CENTRAL_LOG_IP=127.0.0.1
        }
    fi
fi

echo "Using CENTRAL_LOG_IP: $CENTRAL_LOG_IP"

# Function to clean up processes on exit.
cleanup() {
    echo "Stopping all components..."
    kill $CENTRAL_LOG_PID $SIGNALING_PID $RECEIVER_PID 2>/dev/null
    echo "All components stopped."
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "Starting central_log_server..."
python3 central_log_server.py &
CENTRAL_LOG_PID=$!
echo "central_log_server started with PID $CENTRAL_LOG_PID"

echo "Starting signaling_server..."
python3 signaling_server.py &
SIGNALING_PID=$!
echo "signaling_server started with PID $SIGNALING_PID"

sleep 2

echo "Starting receiver..."
python3 receiver.py --signaling ws://localhost:8000 --room testroom &
RECEIVER_PID=$!
echo "receiver started with PID $RECEIVER_PID"

echo "Host components started."
echo "Note: The sender must be launched on the remote machine to share its screen."
echo "Press [ENTER] to stop everything."
read -r
cleanup
