import speedtest
import sqlite3
from datetime import datetime
import asyncio
import logging
import json

class SpeedTestManager:
    def __init__(self, db_path='/home/pi/app/speedtests.db'):
        self.db_path = db_path
        self._create_table()
    
    def _create_table(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS speedtests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                download REAL,
                upload REAL,
                latency REAL,
                jitter REAL,
                server TEXT
            )''')
    
    async def run_test(self):
        try:
            st = speedtest.Speedtest()
            st.get_best_server()
            st.download()
            st.upload()
            
            results = {
                'timestamp': datetime.utcnow().isoformat(),
                'download': st.results.download / 1_000_000,
                'upload': st.results.upload / 1_000_000,
                'latency': st.results.ping,
                'jitter': st.results.jitter,
                'server': json.dumps(st.results.server)
            }
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''INSERT INTO speedtests 
                    (timestamp, download, upload, latency, jitter, server)
                    VALUES (?,?,?,?,?,?)''',
                    (results['timestamp'], results['download'],
                     results['upload'], results['latency'],
                     results['jitter'], results['server']))
            
            return results
        except Exception as e:
            logging.error(f"Speedtest failed: {str(e)}")
            return None
