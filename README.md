# Smart Sensor Network using Modbus TCP

This project implements a complete Modbus TCP-based smart sensor network system, consisting of:

1. Simulated Modbus TCP servers (industrial sensors)
2. A SCADA-like Modbus client that polls and logs data
3. Persistent storage using SQLite
4. Web dashboard for real-time monitoring and visualization

## System Architecture

[Multiple Simulated Sensors (Modbus TCP Servers)]
↕ (TCP/Port 5020/5021...)
↕
[Network]
↕
[Modbus Client (Poller / SCADA)] --> [SQLite DB]
↕
[Dashboard Web App]
↕
User (browser)

basic


## Features

- **Modbus TCP Servers**: Simulate temperature and humidity sensors with configurable parameters.
- **Modbus TCP Client**: Polls multiple servers, processes readings, and stores data.
- **Database**: SQLite for lightweight but persistent storage of sensor readings.
- **Dashboard**: Real-time visualization of sensor data, historical trends, and alarm monitoring.
- **Alarms**: Detect and display abnormal conditions (temperature/humidity too high/low).

## Requirements

- Python 3.10 or higher
- Dependencies listed in `requirements.txt`

## Installation

1. Clone this repository:
git clone https://github.com/boya-dotcom/TCP_Modbus_Capstone_App.git
cd TCP_Modbus_Capstone_App



2. Create and activate a virtual environment:
python -m venv venv
source venv/bin/activate # On Windows: venv\Scripts\activate



3. Install dependencies:
pip install -r requirements.txt

livecodeserver


## Running the System

### Using the run script

The easiest way to run the complete system is by using the provided run script:

chmod +x run.sh # Make the script executable (Unix/Linux)
./run.sh start # Start all components

nsis


The run script provides the following commands:
- `start`: Start all components
- `stop`: Stop all components
- `restart`: Restart all components
- `status`: Check the status of all components
- `test`: Run tests

### Manual Startup

Alternatively, you can start each component manually:

1. Start the Modbus TCP Servers (in separate terminals):
python server/modbus_server.py --port 5020 --id 1
python server/modbus_server.py --port 5021 --id 2



2. Start the Modbus TCP Client:
python client/modbus_client.py --config client/config.yaml



3. Start the Dashboard Web App:
python dashboard/app.py



4. Open the dashboard in  web browser:
http://localhost:5000

yaml


## Configuration

### Server Configuration

Edit `server/config.yaml` to change sensor simulation parameters:

```yaml
update_rate: 1.0  # seconds between updates
temp_range: [15, 30]  # min, max temper)
humidity_range: [30, 80]  # min, max humidity (%)
deterministic: false  # use deterministic pattern instead of random
seed: 42  # random seed for deterministic mode
Client Configuration
Edit client/config.yaml to configure sensor polling:

yaml

db_path: "readings.db"
sensors:
  - id: 1
    host: "localhost"
    port: 5020
    poll_rate: 5.0  # seconds between polls
  - id: 2
    host: "localhost"
    port: 5021
    poll_rate: 10.0
Project Structure
basic

modbus-capstone/
├─ server/           # Modbus TCP Server (simulated sensors)
├─ client/           # Modbus TCP Client (poller/SCADA)
├─ dashboard/        # Web dashboard
├─ requirements.txt  # Dependencies
├─ run.sh            # Run script
└─ README.md         # Documentation

Testing
Run the test suite with:


pytest
Future Enhancements
Deploy on Raspberry Pi for physical demonstration
Add user authentication for the dashboard
Implement email notifications for alarms
Dockerize all components for easy deployment

Add more sensor types and Modbus function codescd
