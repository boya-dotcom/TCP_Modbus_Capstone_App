# simple_modbus_server.py
import random
import time
import threading
import logging
import argparse

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Import from PyModbus 3.11.x - using correct import paths
try:
    from pymodbus import __version__ as pymodbus_version
    logger.info(f"PyModbus version: {pymodbus_version}")
    
    # Import the correct modules for PyModbus 3.11.x
    from pymodbus.datastore import ModbusSparseDataBlock
    from pymodbus.datastore.context import ModbusServerContext, ModbusSlaveContext
    from pymodbus.server.async_io import StartTcpServer
    
    logger.info("Successfully imported PyModbus 3.11.x modules")
except ImportError as e:
    logger.error(f"Import error: {e}")
    logger.info("Trying alternate imports...")
    try:
        # Try alternate imports for PyModbus 3.x
        from pymodbus.datastore import ModbusSequentialDataBlock
        from pymodbus.datastore.context import ModbusServerContext, ModbusSlaveContext
        from pymodbus.server.async_io import StartTcpServer
        logger.info("Successfully imported alternate PyModbus 3.x modules")
    except ImportError as e2:
        logger.error(f"Alternate import error: {e2}")
        logger.error("Please install PyModbus 3.x with: pip install pymodbus>=3.0.0")
        exit(1)

class SensorSimulator:
    def __init__(self, context, slave_id=1):
        self.context = context
        self.slave_id = slave_id
        self.running = False
        self.thread = None
    
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info(f"Simulator started for slave {self.slave_id}")
    
    def _run(self):
        while self.running:
            # Generate random values
            temp = random.uniform(15, 30)
            humidity = random.uniform(30, 80)
            
            # Scale for registers
            temp_reg = int(temp * 10)
            hum_reg = int(humidity * 10)
            status_reg = 0
            
            # Status flags for alarms
            if temp > 28:
                status_reg |= 1  # High temp
            if temp < 17:
                status_reg |= 2  # Low temp
            if humidity > 75:
                status_reg |= 4  # High humidity
            if humidity < 35:
                status_reg |= 8  # Low humidity
            
            # Update registers
            # In PyModbus 3.11.x, context has slaves attribute
            slave = self.context[self.slave_id]
            slave.setValues(3, 0, [temp_reg, hum_reg, status_reg])
            
            logger.info(f"Slave {self.slave_id}: Temp={temp:.1f}°C, Humidity={humidity:.1f}%, Status={status_reg}")
            
            # Wait for next update
            time.sleep(1)
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)

async def run_server(port=5020, slave_id=1):
    logger.info(f"Starting Modbus TCP server on port {port}")
    
    # Create data store - for PyModbus 3.11.x
    try:
        # First try with ModbusSparseDataBlock
        store = ModbusSlaveContext(
            hr=ModbusSparseDataBlock({0: 0, 1: 0, 2: 0}),
            zero_mode=True
        )
        logger.info("Using ModbusSparseDataBlock")
    except:
        # Fall back to ModbusSequentialDataBlock if available
        try:
            from pymodbus.datastore import ModbusSequentialDataBlock
            store = ModbusSlaveContext(
                hr=ModbusSequentialDataBlock(0, [0, 0, 0]),
                zero_mode=True
            )
            logger.info("Using ModbusSequentialDataBlock")
        except ImportError:
            logger.error("Could not create datastore")
            return
    
    # Create server context (dictionary of slave contexts)
    context = ModbusServerContext(slaves={slave_id: store}, single=False)
    
    # Start simulator
    simulator = SensorSimulator(context, slave_id=slave_id)
    simulator.start()
    
    # Start server
    logger.info(f"Starting async Modbus server on port {port}")
    await StartTcpServer(
        context=context,
        address=("0.0.0.0", port)
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='PyModbus 3.11.x TCP Server')
    parser.add_argument('--port', type=int, default=5020, help='TCP port')
    parser.add_argument('--id', type=int, default=1, help='Slave ID')
    
    args = parser.parse_args()
    
    # Run the async server
    import asyncio
    asyncio.run(run_server(port=args.port, slave_id=args.id))