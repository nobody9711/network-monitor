from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
import aiosqlite
import asyncsnmp
import sqlite3
import logging
import asyncio
from datetime import datetime, timedelta
from speedtest import SpeedTestManager
from pydantic import BaseModel

class PiMonitor:
    def __init__(self):
        self.devices = {}
        self.alert_rules = {}
        self.pihole_stats = {}
    
    @classmethod
    async def lifespan(cls, app: FastAPI):
        app.state.monitor = cls()
        yield
        # Cleanup resources

app = FastAPI(lifespan=PiMonitor.lifespan)

# CORS Configuration
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:*", "http://*.local"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Speedtest Integration
@app.on_event("startup")
async def startup_event():
    app.state.speedtest_manager = SpeedTestManager()
    asyncio.create_task(hourly_test_task(app.state.speedtest_manager))
    asyncio.create_task(poll_devices())

async def hourly_test_task(manager):
    while True:
        await manager.run_test()
        await asyncio.sleep(3600)

async def poll_devices():
    while True:
        try:
            # Pi-hole API integration
            async with aiohttp.ClientSession() as session:
                pihole_resp = await session.get('http://localhost/admin/api.php')
                app.state.monitor.pihole_stats = await pihole_resp.json()
            
            # Unbound stats collection
            unbound_resp = await asyncsnmp.get(
                targets=['127.0.0.1'],
                community='public',
                oids=['1.3.6.1.4.1.12325.1.200.0']  # Example OID
            )
            # Process SNMP response
            
        except Exception as e:
            logging.error(f"Device polling error: {str(e)}")
        await asyncio.sleep(300)  # 5 minute interval

# API Endpoints
@app.get("/health")
async def health_check():
    return {"status": "active", "version": "1.4.0"}

@app.get("/pihole/stats")
async def get_pihole_stats():
    return app.state.monitor.pihole_stats

@app.get("/speedtest/results")
async def get_speedtest_results(start: str = None, end: str = None):
    start_date, end_date = validate_time_window(start, end)
    
    with sqlite3.connect('/home/pi/app/speedtests.db') as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM speedtests
            WHERE timestamp BETWEEN ? AND ?
            ORDER BY timestamp
        ''', (start_date.isoformat(), end_date.isoformat()))
        
        return [dict(row) for row in cursor.fetchall()]

@app.post("/speedtest/trigger")
async def manual_trigger_test():
    return await app.state.speedtest_manager.run_test()

def validate_time_window(start: str = None, end: str = None):
    if not start and not end:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=1)
        return start_date, end_date
    try:
        start_date = datetime.fromisoformat(start) if start else datetime.min
        end_date = datetime.fromisoformat(end) if end else datetime.max
        return start_date, end_date
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid timestamp format")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
