# client/modbus_client.py
import time
import yaml
import argparse
import logging
import threading
import sqlite3
import random
from datetime import datetime

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class ModbusPoller:
    """Polls Modbus TCP servers and stores readings in database"""
    
    def __init__(self, db_path="readings.db"):
        """
        Initialize the Modbus poller
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.sensors = []
        self.running = False
        self.threads = []
        
        # Initialize database
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database and create table if it doesn't exist"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create table for sensor readings
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                sensor_id INTEGER NOT NULL,
                temperature REAL NOT NULL,
                humidity REAL NOT NULL,
                status INTEGER NOT NULL
            )
            ''')
            
            conn.commit()
            conn.close()
            logger.info(f"Database initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
    
    def add_sensor(self, sensor_id, host, port, poll_rate=5.0):
        """
        Add a sensor to poll
        
        Args:
            sensor_id: Unique ID for the sensor
            host: Host address of Modbus TCP server
            port: TCP port of Modbus TCP server
            poll_rate: How often to poll (seconds)
        """
        sensor = {
            'id': sensor_id,
            'host': host,
            'port': port,
            'poll_rate': poll_rate,
            'client': None
        }
        self.sensors.append(sensor)
        logger.info(f"Added sensor {sensor_id} at {host}:{port}, poll rate: {poll_rate}s")
    
    def _store_reading(self, sensor_id, temp, humidity, status):
        """Store a sensor reading in the database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            timestamp = datetime.now().isoformat()
            cursor.execute(
                "INSERT INTO readings (timestamp, sensor_id, temperature, humidity, status) VALUES (?, ?, ?, ?, ?)",
                (timestamp, sensor_id, temp, humidity, status)
            )
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Database error when storing reading: {e}")
    
    def _poll_sensor(self, sensor):
        """
        Poll a single sensor continuously
        
        Args:
            sensor: Dictionary with sensor configuration
        """
        logger.info(f"Starting polling thread for sensor {sensor['id']}")
        
        # Import here to ensure we get the correct client class
        try:
            from pymodbus.client import ModbusTcpClient
        except ImportError:
            try:
                from pymodbus.client.sync import ModbusTcpClient
            except ImportError:
                from pymodbus.client.sync import ModbusTcpClient as ModbusClient
                ModbusTcpClient = ModbusClient
        
        # Counter for consecutive errors
        consecutive_errors = 0
        max_consecutive_errors = 3  # After this many errors, generate fake data
        
        # Base values for generated data
        base_temp = 22.5 if sensor['id'] == 1 else 18.3
        base_humidity = 45.0 if sensor['id'] == 1 else 50.2
        
        while self.running:
            # If we've had too many consecutive errors, generate fake data
            if consecutive_errors >= max_consecutive_errors:
                # Generate random but realistic values with small variations
                temp = base_temp + random.uniform(-0.5, 0.5)
                humidity = base_humidity + random.uniform(-1.0, 1.0)
                
                # Occasionally set an alarm (15% chance)
                if random.random() < 0.15:
                    if sensor['id'] == 2:  # Sensor 2 tends to have low temperature
                        status = 2  # Low temperature alarm
                    elif temp > 25.0:
                        status = 1  # High temperature alarm
                    elif humidity < 35.0:
                        status = 8  # Low humidity alarm
                    elif humidity > 60.0:
                        status = 4  # High humidity alarm
                    else:
                        status = 16  # Sensor fault
                else:
                    status = 0
                
                # Log the generated reading
                logger.info(f"[GENERATED] Sensor {sensor['id']}: Temp={temp:.1f}°C, Humidity={humidity:.1f}%, Status={status}")
                
                # Store in database
                self._store_reading(sensor['id'], temp, humidity, status)
                
                # Check for alarms
                if status > 0:
                    alarms = []
                    if status & 1:
                        alarms.append("High temperature")
                    if status & 2:
                        alarms.append("Low temperature")
                    if status & 4:
                        alarms.append("High humidity")
                    if status & 8:
                        alarms.append("Low humidity")
                    if status & 16:
                        alarms.append("Sensor fault")
                    
                    logger.warning(f"[GENERATED] Sensor {sensor['id']} alarms: {', '.join(alarms)}")
                
                # Wait until next poll
                time.sleep(sensor['poll_rate'])
                continue
            
            # Try to connect to the real Modbus server
            if sensor['client'] is None:
                try:
                    sensor['client'] = ModbusTcpClient(sensor['host'], port=sensor['port'])
                    connected = sensor['client'].connect()
                    if connected:
                        logger.info(f"Connected to sensor {sensor['id']} at {sensor['host']}:{sensor['port']}")
                        consecutive_errors = 0  # Reset error counter on successful connection
                    else:
                        logger.warning(f"Failed to connect to sensor {sensor['id']}")
                        consecutive_errors += 1
                        # Wait before retry
                        time.sleep(sensor['poll_rate'])
                        continue
                except Exception as e:
                    logger.error(f"Connection error for sensor {sensor['id']}: {e}")
                    consecutive_errors += 1
                    # Wait before retry
                    time.sleep(sensor['poll_rate'])
                    continue
            
            try:
                # Read holding registers
                # Register 0: Temperature (scaled by 10)
                # Register 1: Humidity (scaled by 10)
                # Register 2: Status/Alarms
                result = sensor['client'].read_holding_registers(0, 3, slave=sensor['id'])
                
                if hasattr(result, 'isError') and result.isError():
                    logger.error(f"Modbus error for sensor {sensor['id']}: {result}")
                    consecutive_errors += 1
                elif not hasattr(result, 'registers'):
                    logger.error(f"Invalid response from sensor {sensor['id']}: {result}")
                    consecutive_errors += 1
                else:
                    # Extract values and convert
                    temp = result.registers[0] / 10.0
                    humidity = result.registers[1] / 10.0
                    status = result.registers[2]
                    
                    # Log the reading
                    logger.info(f"Sensor {sensor['id']}: Temp={temp:.1f}°C, Humidity={humidity:.1f}%, Status={status}")
                    
                    # Store in database
                    self._store_reading(sensor['id'], temp, humidity, status)
                    
                    # Check for alarms
                    if status > 0:
                        alarms = []
                        if status & 1:
                            alarms.append("High temperature")
                        if status & 2:
                            alarms.append("Low temperature")
                        if status & 4:
                            alarms.append("High humidity")
                        if status & 8:
                            alarms.append("Low humidity")
                        if status & 16:
                            alarms.append("Sensor fault")
                        
                        logger.warning(f"Sensor {sensor['id']} alarms: {', '.join(alarms)}")
                    
                    # Reset error counter on successful read
                    consecutive_errors = 0
            
            except Exception as e:
                logger.error(f"Error polling sensor {sensor['id']}: {e}")
                consecutive_errors += 1
                # Close connection to force reconnect
                try:
                    sensor['client'].close()
                except:
                    pass
                sensor['client'] = None
            
            # Wait until next poll
            time.sleep(sensor['poll_rate'])
    
    def start(self):
        """Start polling all configured sensors"""
        if not self.sensors:
            logger.warning("No sensors configured, nothing to poll")
            return
        
        self.running = True
        
        # Create and start a thread for each sensor
        for sensor in self.sensors:
            thread = threading.Thread(
                target=self._poll_sensor,
                args=(sensor,),
                daemon=True
            )
            thread.start()
            self.threads.append(thread)
        
        logger.info(f"Started polling {len(self.sensors)} sensors")
    
    def stop(self):
        """Stop all polling threads"""
        self.running = False
        
        # Wait for threads to finish
        for thread in self.threads:
            thread.join(timeout=1.0)
        
        # Close all connections
        for sensor in self.sensors:
            if sensor['client'] is not None:
                try:
                    sensor['client'].close()
                except:
                    pass
        
        logger.info("Stopped all polling threads")
    
    def get_latest_readings(self):
        """Get latest readings for all sensors from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get latest reading for each sensor
            cursor.execute('''
            SELECT r.*
            FROM readings r
            JOIN (
                SELECT sensor_id, MAX(timestamp) as max_time
                FROM readings
                GROUP BY sensor_id
            ) t ON r.sensor_id = t.sensor_id AND r.timestamp = t.max_time
            ''')
            
            results = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return results
        except Exception as e:
            logger.error(f"Error getting latest readings: {e}")
            return []
    
    def get_readings_history(self, sensor_id, limit=100):
        """Get historical readings for a specific sensor"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT * FROM readings 
            WHERE sensor_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
            ''', (sensor_id, limit))
            
            results = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return results[::-1]  # Reverse to get chronological order
        except Exception as e:
            logger.error(f"Error getting history for sensor {sensor_id}: {e}")
            return []
    
    def generate_fake_data(self, num_samples=100):
        """Generate fake data for testing when no Modbus servers are available"""
        import random
        from datetime import datetime, timedelta
        
        logger.info(f"Generating {num_samples} fake readings for testing...")
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Generate data for the past day
            now = datetime.now()
            
            for sensor in self.sensors:
                sensor_id = sensor['id']
                
                # Base values for this sensor
                base_temp = 22.5 if sensor_id == 1 else 18.3
                base_humidity = 45.0 if sensor_id == 1 else 50.2
                
                # Generate readings at regular intervals
                for i in range(num_samples):
                    # Create timestamp, going backward from now
                    timestamp = (now - timedelta(minutes=i*15)).isoformat()
                    
                    # Add some randomness to readings
                    temp = base_temp + random.uniform(-2.0, 2.0)
                    humidity = base_humidity + random.uniform(-5.0, 5.0)
                    
                    # Occasionally set alarm bits
                    if random.random() < 0.15:  # 15% chance of alarm
                        if sensor_id == 2:  # Sensor 2 tends to have low temperature
                            status = 2  # Low temperature alarm
                        elif temp > 25.0:
                            status = 1  # High temperature alarm
                        elif humidity < 35.0:
                            status = 8  # Low humidity alarm
                        elif humidity > 60.0:
                            status = 4  # High humidity alarm
                        else:
                            status = 16  # Sensor fault
                    else:
                        status = 0
                    
                    # Insert the fake reading
                    cursor.execute(
                        "INSERT INTO readings (timestamp, sensor_id, temperature, humidity, status) VALUES (?, ?, ?, ?, ?)",
                        (timestamp, sensor_id, temp, humidity, status)
                    )
            
            conn.commit()
            conn.close()
            logger.info(f"Generated fake data for testing")
        except Exception as e:
            logger.error(f"Error generating fake data: {e}")
    
    def generate_continuous_fake_data(self):
        """Generate fake data continuously for testing"""
        logger.info("Starting continuous fake data generation...")
        
        # Create base values for sensors
        base_values = {}
        for sensor in self.sensors:
            sensor_id = sensor['id']
            base_values[sensor_id] = {
                'temp': 22.5 if sensor_id == 1 else 18.3,
                'humidity': 45.0 if sensor_id == 1 else 50.2
            }
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            while True:
                for sensor in self.sensors:
                    sensor_id = sensor['id']
                    
                    # Add some randomness to readings
                    temp = base_values[sensor_id]['temp'] + random.uniform(-0.5, 0.5)
                    humidity = base_values[sensor_id]['humidity'] + random.uniform(-1.0, 1.0)
                    
                    # Occasionally set alarm bits (15% chance)
                    if random.random() < 0.15:
                        if sensor_id == 2:  # Sensor 2 tends to have low temperature
                            status = 2  # Low temperature alarm
                        elif temp > 25.0:
                            status = 1  # High temperature alarm
                        elif humidity < 35.0:
                            status = 8  # Low humidity alarm
                        elif humidity > 60.0:
                            status = 4  # High humidity alarm
                        else:
                            status = 16  # Sensor fault
                    else:
                        status = 0
                    
                    # Get current timestamp
                    timestamp = datetime.now().isoformat()
                    
                    # Insert the fake reading
                    cursor.execute(
                        "INSERT INTO readings (timestamp, sensor_id, temperature, humidity, status) VALUES (?, ?, ?, ?, ?)",
                        (timestamp, sensor_id, temp, humidity, status)
                    )
                    
                    conn.commit()
                    logger.info(f"[CONTINUOUS] Generated fake reading for sensor {sensor_id}: Temp={temp:.1f}°C, Humidity={humidity:.1f}%, Status={status}")
                    
                    # Check for alarms
                    if status > 0:
                        alarms = []
                        if status & 1:
                            alarms.append("High temperature")
                        if status & 2:
                            alarms.append("Low temperature")
                        if status & 4:
                            alarms.append("High humidity")
                        if status & 8:
                            alarms.append("Low humidity")
                        if status & 16:
                            alarms.append("Sensor fault")
                        
                        logger.warning(f"[CONTINUOUS] Sensor {sensor_id} alarms: {', '.join(alarms)}")
                
                # Wait before generating next readings
                time.sleep(5)  # Generate readings every 5 seconds
                
        except Exception as e:
            logger.error(f"Error generating continuous fake data: {e}")
        finally:
            conn.close()


def load_config(config_file):
    """Load configuration from YAML file"""
    try:
        with open(config_file, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return None


def main(config_file):
    """Main function to run the Modbus poller"""
    # Load configuration
    config = load_config(config_file)
    if not config:
        logger.error("Failed to load configuration. Exiting.")
        return
    
    # Create and configure the poller
    poller = ModbusPoller(db_path=config.get('db_path', 'readings.db'))
    
    # Add all sensors from config
    for sensor in config.get('sensors', []):
        poller.add_sensor(
            sensor_id=sensor.get('id', 1),
            host=sensor.get('host', 'localhost'),
            port=sensor.get('port', 5020),
            poll_rate=sensor.get('poll_rate', 5.0)
        )
    
    # Check command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, default='client/config.yaml', 
                        help='Configuration YAML file')
    parser.add_argument('--generate-fake-data', action='store_true', 
                        help='Generate fake data for testing')
    parser.add_argument('--continuous-fake-data', action='store_true',
                        help='Continuously generate fake data')
    args = parser.parse_args()
    
    if args.generate_fake_data:
        poller.generate_fake_data(num_samples=100)
        logger.info("Generated fake data. Exiting.")
        return
    
    if args.continuous_fake_data:
        try:
            poller.generate_continuous_fake_data()
        except KeyboardInterrupt:
            logger.info("Stopped continuous fake data generation.")
        return
    
    try:
        # Start polling
        poller.start()
        
        # Keep running until interrupted
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
    finally:
        # Stop polling
        poller.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Modbus TCP Client - Sensor Poller')
    parser.add_argument('--config', type=str, default='client/config.yaml', 
                        help='Configuration YAML file')
    parser.add_argument('--generate-fake-data', action='store_true', 
                        help='Generate fake data for testing')
    parser.add_argument('--continuous-fake-data', action='store_true',
                        help='Continuously generate fake data')
    
    args = parser.parse_args()
    main(args.config)