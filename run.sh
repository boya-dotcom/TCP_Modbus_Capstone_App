#!/bin/bash
# run.sh

# Function to check if a program is running
is_running() {
    pgrep -f "$1" > /dev/null
}

# Stop any existing processes
stop_processes() {
    echo "Stopping existing processes..."
    pkill -f "python server/modbus_server.py" || true
    pkill -f "python client/modbus_client.py" || true
    pkill -f "python dashboard/app.py" || true
    sleep 1
}

# Start everything
start_all() {
    echo "Starting Modbus TCP Server 1 (port 5020)..."
    python server/modbus_server.py --port 5020 --id 1 &
    sleep 2
    
    echo "Starting Modbus TCP Server 2 (port 5021)..."
    python server/modbus_server.py --port 5021 --id 2 &
    sleep 2
    
    echo "Starting Modbus TCP Client..."
    python client/modbus_client.py --config client/config.yaml &
    sleep 2
    
    echo "Starting Dashboard Web App..."
    python dashboard/app.py &
    
    echo "All components started!"
    echo "Dashboard available at: http://localhost:5000"
}

# Create test configuration
create_test_config() {
    # Server 1 config
    cat > server/config.yaml << EOF
update_rate: 1.0
temp_range: [15, 30]
humidity_range: [30, 80]
deterministic: false
seed: 42
EOF

    # Client config
    cat > client/config.yaml << EOF
db_path: "readings.db"
sensors:
  - id: 1
    host: "localhost"
    port: 5020
    poll_rate: 5.0
  - id: 2
    host: "localhost"
    port: 5021
    poll_rate: 10.0
EOF
}

# Function to display help
show_help() {
    echo "Modbus TCP Capstone Project"
    echo "Usage: ./run.sh [command]"
    echo ""
    echo "Commands:"
    echo "  start    - Start all components"
    echo "  stop     - Stop all components"
    echo "  restart  - Restart all components"
    echo "  status   - Check component status"
    echo "  test     - Run tests"
    echo "  help     - Show this help message"
}

# Check command line arguments
case "$1" in
    start)
        stop_processes
        create_test_config
        start_all
        ;;
    stop)
        stop_processes
        echo "All processes stopped."
        ;;
    restart)
        stop_processes
        create_test_config
        start_all
        ;;
    status)
        echo "Checking component status..."
        if is_running "python server/modbus_server.py"; then
            echo "✅ Modbus TCP Server is running"
        else
            echo "❌ Modbus TCP Server is NOT running"
        fi
        
        if is_running "python client/modbus_client.py"; then
            echo "✅ Modbus TCP Client is running"
        else
            echo "❌ Modbus TCP Client is NOT running"
        fi
        
        if is_running "python dashboard/app.py"; then
            echo "✅ Dashboard Web App is running"
        else
            echo "❌ Dashboard Web App is NOT running"
        fi
        ;;
    test)
        echo "Running tests..."
        pytest -q
        ;;
    *)
        show_help
        ;;
esac