"""
InfluxDB wrapper for writing and querying telemetry.
"""
import os
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
import pandas as pd
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

load_dotenv()


class InfluxClient:
    def __init__(self):
        self.url = os.getenv('INFLUX_URL', 'http://localhost:8086')
        self.token = os.getenv('INFLUX_TOKEN')
        self.org = os.getenv('INFLUX_ORG', 'healing-system')
        self.bucket = os.getenv('INFLUX_BUCKET', 'telemetry')
        self.client = InfluxDBClient(url=self.url, token=self.token, org=self.org)
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        self.query_api = self.client.query_api()

    def write(self, readings: list) -> None:
        """Write a list of TelemetryReading objects to InfluxDB."""
        points = []
        for r in readings:
            point = (
                Point(r.source)
                .tag("component", r.component)
                .tag("metric", r.metric)
                .field("value", float(r.value))
                .time(r.timestamp, WritePrecision.NS)
            )
            points.append(point)

        retries = 3
        for attempt in range(retries):
            try:
                self.write_api.write(bucket=self.bucket, record=points)
                return
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    print(f"InfluxDB write failed after {retries} attempts: {e}")

    def query_range(self, metric: str, component: str, start_hours_ago: int, end_hours_ago: int = 0) -> pd.DataFrame:
        """Query a metric over a time range, returns DataFrame with time and value columns."""
        start = f"-{start_hours_ago}h"
        stop = f"-{end_hours_ago}h" if end_hours_ago > 0 else "now()"

        flux = f'''
        from(bucket: "{self.bucket}")
          |> range(start: {start}, stop: {stop})
          |> filter(fn: (r) => r["metric"] == "{metric}")
          |> filter(fn: (r) => r["component"] == "{component}")
          |> keep(columns: ["_time", "_value"])
        '''

        try:
            result = self.query_api.query_data_frame(flux)
            if result is None or (isinstance(result, pd.DataFrame) and result.empty):
                return pd.DataFrame(columns=['time', 'value'])
            if isinstance(result, list):
                result = pd.concat(result)
            result = result.rename(columns={'_time': 'time', '_value': 'value'})
            return result[['time', 'value']].reset_index(drop=True)
        except Exception as e:
            print(f"InfluxDB query failed: {e}")
            return pd.DataFrame(columns=['time', 'value'])

    def query_latest(self, metric: str, component: str):
        """Get the most recent reading for a metric."""
        flux = f'''
        from(bucket: "{self.bucket}")
          |> range(start: -1h)
          |> filter(fn: (r) => r["metric"] == "{metric}")
          |> filter(fn: (r) => r["component"] == "{component}")
          |> last()
        '''
        try:
            result = self.query_api.query_data_frame(flux)
            if result is None or (isinstance(result, pd.DataFrame) and result.empty):
                return None
            if isinstance(result, list):
                result = pd.concat(result)
            return float(result['_value'].iloc[-1])
        except Exception as e:
            print(f"InfluxDB latest query failed: {e}")
            return None

    def close(self):
        self.client.close()