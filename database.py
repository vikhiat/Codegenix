"""
NeuroFlow Database Backend
Handles all database operations for storing traffic records
"""

import sqlite3
from datetime import datetime, timedelta
import json
import pandas as pd
from pathlib import Path


class TrafficDatabase:
    """Database handler for NeuroFlow traffic records"""
    
    def __init__(self, db_path='neuroflow_data.db'):
        """Initialize database connection and create tables if needed"""
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self._connect()
        self._create_tables()
    
    def _connect(self):
        """Establish database connection"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
    
    def _create_tables(self):
        """Create database tables if they don't exist"""
        
        # Traffic Records Table - stores every detection event
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS traffic_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                lane_id INTEGER NOT NULL,
                vehicle_count INTEGER NOT NULL,
                congestion_level TEXT,
                green_duration INTEGER,
                CONSTRAINT valid_lane CHECK (lane_id IN (1, 2))
            )
        ''')
        
        # Decision Log Table - stores traffic control decisions
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS decision_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                lane1_vehicles INTEGER NOT NULL,
                lane2_vehicles INTEGER NOT NULL,
                lane1_duration INTEGER NOT NULL,
                lane2_duration INTEGER NOT NULL,
                total_vehicles INTEGER NOT NULL,
                congestion_level TEXT NOT NULL,
                active_lane INTEGER NOT NULL
            )
        ''')
        
        # Session Statistics Table - stores aggregate session data
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS session_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_start DATETIME DEFAULT CURRENT_TIMESTAMP,
                session_end DATETIME,
                total_detections INTEGER DEFAULT 0,
                total_decisions INTEGER DEFAULT 0,
                avg_lane1_vehicles REAL DEFAULT 0.0,
                avg_lane2_vehicles REAL DEFAULT 0.0,
                peak_congestion_level TEXT,
                session_duration_seconds INTEGER
            )
        ''')
        
        self.conn.commit()
    
    def add_traffic_record(self, lane_id, vehicle_count, congestion_level=None, green_duration=None):
        """
        Add a traffic detection record
        """
        try:
            self.cursor.execute('''
                INSERT INTO traffic_records 
                (lane_id, vehicle_count, congestion_level, green_duration)
                VALUES (?, ?, ?, ?)
            ''', (lane_id, vehicle_count, congestion_level, green_duration))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error adding traffic record: {e}")
            return False
    
    def add_decision(self, lane1_vehicles, lane2_vehicles, lane1_duration, 
                     lane2_duration, congestion_level, active_lane):
        """
        Add a traffic control decision to the log
        """
        try:
            total_vehicles = lane1_vehicles + lane2_vehicles
            self.cursor.execute('''
                INSERT INTO decision_log 
                (lane1_vehicles, lane2_vehicles, lane1_duration, lane2_duration,
                 total_vehicles, congestion_level, active_lane)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (lane1_vehicles, lane2_vehicles, lane1_duration, lane2_duration,
                  total_vehicles, congestion_level, active_lane))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error adding decision: {e}")
            return False
    
    def get_recent_records(self, limit=50):
        """Get recent traffic records"""
        self.cursor.execute('''
            SELECT * FROM traffic_records 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,))
        
        columns = [description[0] for description in self.cursor.description]
        results = self.cursor.fetchall()
        return [dict(zip(columns, row)) for row in results]
    
    def get_recent_decisions(self, limit=20):
        """Get recent decision log entries"""
        self.cursor.execute('''
            SELECT * FROM decision_log 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,))
        
        columns = [description[0] for description in self.cursor.description]
        results = self.cursor.fetchall()
        return [dict(zip(columns, row)) for row in results]
    
    def get_statistics(self, time_period='all'):
        """
        Get traffic statistics
        """
        # Build time filter
        time_filter = ""
        if time_period == 'today':
            time_filter = "WHERE DATE(timestamp) = DATE('now')"
        elif time_period == 'week':
            time_filter = "WHERE timestamp >= datetime('now', '-7 days')"
        elif time_period == 'hour':
            time_filter = "WHERE timestamp >= datetime('now', '-1 hour')"
        
        # Get statistics
        stats = {}
        
        # Total records
        self.cursor.execute(f"SELECT COUNT(*) FROM traffic_records {time_filter}")
        stats['total_records'] = self.cursor.fetchone()[0]
        
        # Average vehicles per lane
        self.cursor.execute(f'''
            SELECT lane_id, AVG(vehicle_count) as avg_count, MAX(vehicle_count) as max_count
            FROM traffic_records {time_filter}
            GROUP BY lane_id
        ''')
        lane_stats = self.cursor.fetchall()
        stats['lane_stats'] = {f'lane_{row[0]}': {'avg': row[1], 'max': row[2]} 
                               for row in lane_stats}
        
        # Congestion distribution
        self.cursor.execute(f'''
            SELECT congestion_level, COUNT(*) as count
            FROM decision_log {time_filter}
            GROUP BY congestion_level
        ''')
        congestion_data = self.cursor.fetchall()
        stats['congestion_distribution'] = {row[0]: row[1] for row in congestion_data if row[0]}
        
        # Total decisions made
        self.cursor.execute(f"SELECT COUNT(*) FROM decision_log {time_filter}")
        stats['total_decisions'] = self.cursor.fetchone()[0]
        
        return stats
    
    def get_daily_analytics(self, days=30):
        """
        Get daily traffic analytics for the last N days
        Returns aggregated data for charts
        """
        try:
            # Calculate date N days ago
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            # Simple aggregation by date
            self.cursor.execute('''
                SELECT 
                    DATE(timestamp) as date,
                    AVG(vehicle_count) as avg_vehicles,
                    MAX(vehicle_count) as max_vehicles,
                    SUM(vehicle_count) as total_volume
                FROM traffic_records
                WHERE timestamp >= ?
                GROUP BY DATE(timestamp)
                ORDER BY date
            ''', (start_date,))
            
            columns = [description[0] for description in self.cursor.description]
            results = self.cursor.fetchall()
            return [dict(zip(columns, row)) for row in results]
        except Exception as e:
            print(f"Error getting daily analytics: {e}")
            return []

    def export_to_csv(self, table_name, filename=None):
        """
        Export table to CSV file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{table_name}_{timestamp}.csv"
        
        try:
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", self.conn)
            df.to_csv(filename, index=False)
            return filename
        except Exception as e:
            print(f"Error exporting to CSV: {e}")
            return None
    
    def export_to_json(self, table_name, filename=None):
        """
        Export table to JSON file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{table_name}_{timestamp}.json"
        
        try:
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", self.conn)
            df.to_json(filename, orient='records', date_format='iso', indent=2)
            return filename
        except Exception as e:
            print(f"Error exporting to JSON: {e}")
            return None
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
