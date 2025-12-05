# server/modbus_server.py
import random
import math
import time
import yaml
import argparse
import logging
import threading
import importlib

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Check PyModbus version and structure
logger.info("Checking PyModbus structure...")

# Import the correct modules based on your PyModbus version
try:
    # Try to detect the PyModbus structure
    from pymodbus import __version__ as pymodbus_version
    logger.info(f"PyModbus version: {pymodbus_version}")
    
    # Print available modules in pymodbus.datastore for debugging
    import pkgutil
    import pymodbus.datastore
    logger.info("Available modules in pymodbus.datastore:")
    for importer, modname, ispkg in pkgutil.iter_modules(pymodbus.datastore.__path__):
        logger.info(f" - {modname}")
    
    # Import relevant modules from store submodule
    from pymodbus.datastore.store import ModbusSequentialDataBlock
    from pymodbus.datastore.store import ModbusSlaveContext
    from pymodbus.datastore.store import ModbusServerContext
    logger.info("Successfully imported from pymodbus.datastore.store")
    
except ImportError as e:
    logger.error(f"Error with import: {e}")
    logger.info("Trying alternative imports...")
    try:
        # Try the newer way first
        from pymodbus.datastore import ModbusServerContext, ModbusSlaveContext, ModbusSequentialDataBlock
        logger.info("Successfully imported from pymodbus.datastore")
    except ImportError:
        logger.info("Falling back to server.sync imports")
        try:
            from pymodbus.server.sync import StartTcpServer
            from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
            logger.info("Successfully imported from pymodbus.server.sync and pymodbus.datastore")
        except ImportError:
            logger.error("Could not find appropriate imports. Please check PyModbus installation.")
            import sys
            sys.exit(1)

# Try different imports for StartTcpServer
try:
    from pymodbus.server import StartTcpServer
    logger.info("Successfully imported StartTcpServer from pymodbus.server")
except ImportError:
    try:
        from pymodbus.server.sync import StartTcpServer
        logger.info("Successfully imported StartTcpServer from pymodbus.server.sync")
    except ImportError:
        logger.error("Could not import StartTcpServer. Please check PyModbus installation.")
        import sys
        sys.exit(1)

class SensorSimulator:
    """Simulates sensor readings and updates Modbus registers"""
    
    def __init__(self, context, slave_id=1, update_rate=1.0, temp_range=(15, 30), 
                 humidity_range=(30, 80), deterministic=False, seed=42):
        """
        Initialize sensor simulator
        
        Args:
            context: Modbus server context
            slave_id: Modbus slave ID
            update_rate: How often to update values (seconds)
            temp_range: Temperature range (min, max)
            humidity_range: Humidity range (min, max)
            deterministic: If True, use fixed pattern instead of random
            seed: Random seed for deterministic mode
        """
        self.context = context
        self.slave_id = slave_id
        self.update_rate = update_rate
        self.temp_range = temp_range
        self.humidity_range = humidity_range
        self.deterministic = deterministic
        self.running = False
        self.thread = None
        self.counter = 0
        
        # Status/alarm register bits:
        # Bit 0: Temperature high alarm (1=alarm)
        # Bit 1: Temperature low alarm (1=alarm)
        # Bit 2: Humidity high alarm (1=alarm)
        # Bit 3: Humidity low alarm (1=alarm)
        # Bit 4: Sensor fault (1=fault)
        # Bits 5-15: Reserved
        
        # Temperature thresholds
        self.temp_high_threshold = temp_range[1] - 2
        self.temp_low_threshold = temp_range[0] + 2
        
        # Humidity thresholds
        self.humidity_high_threshold = humidity_range[1] - 5
        self.humidity_low_threshold = humidity_range[0] + 5
        
        if deterministic:
            random.seed(seed)
    
    def _update_registers(self):
        """Update register values based on simulated readings"""
        if self.deterministic:
            # Generate a sine wave pattern for temp and humidity
            self.counter += 1
            temp_factor = (self.counter % 60) / 60.0  # 0.0 to 1.0 over 60 iterations
            hum_factor = ((self.counter + 30) % 60) / 60.0  # Offset from temp
            
            # Sine wave oscillation between min and max
            temp_range_size = self.temp_range[1] - self.temp_range[0]
            temp = self.temp_range[0] + temp_range_size * (0.5 + 0.5 * math.sin(temp_factor * 2 * math.pi))
            
            hum_range_size = self.humidity_range[1] - self.humidity_range[0]
            humidity = self.humidity_range[0] + hum_range_size * (0.5 + 0.5 * math.sin(hum_factor * 2 * math.pi))
        else:
            # Random values within ranges
            temp = random.uniform(*self.temp_range)
            humidity = random.uniform(*self.humidity_range)
        
        # Scale values for Modbus registers (store as integers with 10x precision)
        temp_reg = int(temp * 10)
        hum_reg = int(humidity * 10)
        
        # Update status/alarm register
        status_reg = 0
        if temp > self.temp_high_threshold:
            status_reg |= 1  # Set bit 0 - high temp alarm
        if temp < self.temp_low_threshold:
            status_reg |= 2  # Set bit 1 - low temp alarm
        if humidity > self.humidity_high_threshold:
            status_reg |= 4  # Set bit 2 - high humidity alarm
        if humidity < self.humidity_low_threshold:
            status_reg |= 8  # Set bit 3 - low humidity alarm
            
        # Occasionally simulate sensor fault (1% chance)
        if random.random() < 0.01 and not self.deterministic:
            status_reg |= 16  # Set bit 4 - sensor fault
        
        # Write to holding registers
        # Register map:
        # 0: Temperature (scaled by 10)
        # 1: Humidity (scaled by 10)
        # 2: Status/Alarms
        slave = self.context[self.slave_id]
        slave.setValues(3, 0, [temp_reg, hum_reg, status_reg])
        
        logger.info(f"Slave {self.slave_id}: Temp={temp:.1f}°C, Humidity={humidity:.1f}%, Status={status_reg}")
    
    def start(self):
        """Start the simulator thread"""
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info(f"Sensor simulator started for slave {self.slave_id}")
    
    def _run(self):
        """Run the simulator, updating values periodically"""
        while self.running:
            self._update_registers()
            time.sleep(self.update_rate)
    
    def stop(self):
        """Stop the simulator thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        logger.info(f"Sensor simulator stopped for slave {self.slave_id}")


def load_config(config_file):
    """Load configuration from YAML file"""
    try:
        with open(config_file, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return None


def setup_server(slave_id=1, port=5020, config_file=None):
    """Setup and run the Modbus TCP server"""
    
    # Default configuration
    config = {
        'update_rate': 1.0,
        'temp_range': [15, 30],
        'humidity_range': [30, 80],
        'deterministic': False,
        'seed': 42
    }
    
    # Override with config file if provided
    if config_file:
        file_config = load_config(config_file)
        if file_config:
            config.update(file_config)
    
    # Initialize data blocks with default values
    # We're using holding registers (function code 3)
    # Register 0: Temperature (scaled by 10)
    # Register 1: Humidity (scaled by 10)
    # Register 2: Status/Alarms
    
    logger.info("Setting up server context...")
    block = ModbusSequentialDataBlock(0, [0, 0, 0])
    store = ModbusSlaveContext(hr=block)
    
    # For newer PyModbus, context is a dictionary of slave contexts
    if hasattr(ModbusServerContext, 'slaves'):
        context = ModbusServerContext(slaves={slave_id: store}, single=False)
    else:
        # For older PyModbus, we need a different approach
        context = ModbusServerContext(slaves=store, single=True)
    
    # Create and start the simulator
    simulator = SensorSimulator(
        context,
        slave_id=slave_id,
        update_rate=config['update_rate'],
        temp_range=config['temp_range'],
        humidity_range=config['humidity_range'],
        deterministic=config['deterministic'],
        seed=config['seed']
    )
    simulator.start()
    
    # Start server
    logger.info(f"Starting Modbus TCP server on port {port} with slave ID {slave_id}")
    try:
        # Check StartTcpServer signature
        import inspect
        sig = inspect.signature(StartTcpServer)
        param_names = list(sig.parameters.keys())
        
        if 'context' in param_names and 'address' in param_names:
            logger.info("Using StartTcpServer with context and address parameters")
            StartTcpServer(context=context, address=("0.0.0.0", port))
        elif len(param_names) >= 2:
            logger.info(f"Using StartTcpServer with positional parameters: {param_names}")
            StartTcpServer(context, address=("0.0.0.0", port))
        else:
            logger.error(f"Unsupported StartTcpServer signature: {sig}")
            simulator.stop()
            return
    except Exception as e:
        logger.error(f"Server error: {e}")
        simulator.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Modbus TCP Server - Sensor Simulator')
    parser.add_argument('--port', type=int, default=5020, help='TCP port')
    parser.add_argument('--id', type=int, default=1, help='Slave ID')
    parser.add_argument('--config', type=str, help='Config YAML file')
    
    args = parser.parse_args()
    setup_server(slave_id=args.id, port=args.port, config_file=args.config)