import os
import sqlite3
from datetime import datetime, timedelta
import time
from flask import Flask, render_template, jsonify, request

app = Flask(__name__, static_url_path='/static', static_folder='static', template_folder='templates')

# Find the database file
db_path = '../readings.db'  # Adjust this path to where your database is located

@app.route('/')
def index():
    """Main dashboard view"""
    try:
        # Connect to the database to get list of sensors
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT sensor_id FROM readings ORDER BY sensor_id")
        sensors = [row['sensor_id'] for row in cursor.fetchall()]
        conn.close()
        
        if not sensors:
            sensors = [1]  # Default sensor if none found
            
        return render_template('index.html', sensors=sensors)
    except Exception as e:
        print(f"Error in index route: {e}")
        # Return basic template with no sensors
        return render_template('index.html', sensors=[1])

@app.route('/api/latest')
def get_latest_readings():
    """API endpoint to get latest readings for all sensors"""
    try:
        # Add cache-busting timestamp to prevent browser caching
        timestamp = request.args.get('t', time.time())
        
        # Connect to the database
        conn = sqlite3.connect(db_path)
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
        
        readings = []
        for row in cursor.fetchall():
            reading = dict(row)
            # Parse status to determine alarms
            status = reading['status']
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
            
            reading['alarms'] = alarms
            readings.append(reading)
        
        conn.close()
        
        # Add timestamp to force the browser to get fresh data
        response = jsonify({'readings': readings, 'timestamp': time.time()})
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        print(f"Error in get_latest_readings: {e}")
        return jsonify({'error': str(e), 'timestamp': time.time()}), 500

@app.route('/api/history/<int:sensor_id>')
def get_sensor_history(sensor_id):
    """API endpoint to get historical readings for a specific sensor"""
    try:
        # Add cache-busting timestamp to prevent browser caching
        timestamp = request.args.get('t', time.time())
        
        # Get query parameters
        hours = request.args.get('hours', 1, type=int)
        
        # Calculate the timestamp for 'hours' ago
        time_ago = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        # Connect to the database
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT * FROM readings 
        WHERE sensor_id = ? AND timestamp > ? 
        ORDER BY timestamp ASC
        ''', (sensor_id, time_ago))
        
        readings = []
        for row in cursor.fetchall():
            readings.append(dict(row))
        
        # Count total readings
        cursor.execute("SELECT COUNT(*) FROM readings")
        total_readings = cursor.fetchone()[0]
        
        conn.close()
        
        # Add timestamp to force the browser to get fresh data
        response = jsonify({
            'sensor_id': sensor_id, 
            'readings': readings, 
            'total_readings': total_readings,
            'timestamp': time.time()
        })
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        print(f"Error in get_sensor_history: {e}")
        return jsonify({'error': str(e), 'timestamp': time.time()}), 500

@app.route('/api/stats')
def get_stats():
    """API endpoint to get dashboard statistics"""
    try:
        # Add cache-busting timestamp to prevent browser caching
        timestamp = request.args.get('t', time.time())
        
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Count unique sensors
        cursor.execute("SELECT COUNT(DISTINCT sensor_id) FROM readings")
        sensor_count = cursor.fetchone()[0]
        
        # Count total readings
        cursor.execute("SELECT COUNT(*) FROM readings")
        total_readings = cursor.fetchone()[0]
        
        # Count readings with alarms (status > 0)
        cursor.execute("SELECT COUNT(*) FROM readings WHERE status > 0")
        alarms_count = cursor.fetchone()[0]
        
        conn.close()
        
        # Add timestamp to force the browser to get fresh data
        response = jsonify({
            'sensor_count': sensor_count,
            'total_readings': total_readings,
            'alarms_count': alarms_count,
            'timestamp': time.time()
        })
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        print(f"Error in get_stats: {e}")
        return jsonify({'error': str(e), 'timestamp': time.time()}), 500

@app.route('/api/debug')
def api_debug():
    """Debug endpoint to verify database access and content"""
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get basic stats
        cursor.execute("SELECT COUNT(*) as count FROM readings")
        total_rows = cursor.fetchone()['count']
        
        # Get the latest 5 readings
        cursor.execute("SELECT * FROM readings ORDER BY timestamp DESC LIMIT 5")
        latest_readings = [dict(row) for row in cursor.fetchall()]
        
        # Check database schema
        cursor.execute("PRAGMA table_info(readings)")
        columns = [dict(row) for row in cursor.fetchall()]
        
        # Check database file info
        db_absolute_path = os.path.abspath(db_path)
        db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0
        db_modified = os.path.getmtime(db_path) if os.path.exists(db_path) else 0
        db_modified_time = datetime.fromtimestamp(db_modified).isoformat()
        
        conn.close()
        
        # Create response with debug info
        debug_info = {
            'db_path': db_absolute_path,
            'db_exists': os.path.exists(db_path),
            'db_size': f"{db_size / 1024:.1f} KB",
            'db_modified': db_modified_time,
            'total_rows': total_rows,
            'latest_readings': latest_readings,
            'columns': columns,
            'current_time': datetime.now().isoformat(),
            'process_id': os.getpid(),
        }
        
        response = jsonify(debug_info)
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    print(f"Using database at: {os.path.abspath(db_path)}")
    app.run(debug=True, host='0.0.0.0')