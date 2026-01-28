#!/usr/bin/env python3
"""
AlphaStock Monitoring Dashboard
Simple web interface to monitor trading system status
"""

from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import subprocess
import sqlite3
from datetime import datetime
import os
from src.utils.timezone_utils import get_current_time, to_ist, to_utc, is_market_hours

class AlphaStockHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            status = self.get_system_status()
            self.wfile.write(json.dumps(status, indent=2).encode())
        
        elif self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            html = self.get_dashboard_html()
            self.wfile.write(html.encode())
        
        else:
            super().do_GET()
    
    def get_system_status(self):
        """Get current system status"""
        status = {
            'timestamp': get_current_time().isoformat(),
            'application': self.check_application(),
            'database': self.check_database(),
            'recent_signals': self.get_recent_signals()
        }
        return status
    
    def check_application(self):
        """Check if main application is running"""
        try:
            with open('alphastock.pid', 'r') as f:
                pid = int(f.read().strip())
            
            # Check if process exists
            result = subprocess.run(['ps', '-p', str(pid)], capture_output=True)
            return {
                'running': result.returncode == 0,
                'pid': pid
            }
        except:
            return {'running': False, 'pid': None}
    
    def check_database(self):
        """Check ClickHouse database status"""
        try:
            result = subprocess.run([
                'docker', 'exec', 'alphastock-clickhouse', 
                'clickhouse-client', '--query', 'SELECT 1'
            ], capture_output=True, text=True)
            
            return {
                'running': result.returncode == 0,
                'connection': 'OK' if result.returncode == 0 else 'Failed'
            }
        except:
            return {'running': False, 'connection': 'Failed'}
    
    def get_recent_signals(self):
        """Get recent trading signals"""
        try:
            if os.path.exists('data/signals/signals.json'):
                with open('data/signals/signals.json', 'r') as f:
                    signals = json.load(f)
                return signals[-5:]  # Last 5 signals
        except:
            pass
        return []
    
    def get_dashboard_html(self):
        """Generate dashboard HTML"""
        return """
<!DOCTYPE html>
<html>
<head>
    <title>AlphaStock Dashboard</title>
    <meta http-equiv="refresh" content="30">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .status { padding: 10px; margin: 10px 0; border-radius: 5px; }
        .running { background-color: #d4edda; color: #155724; }
        .stopped { background-color: #f8d7da; color: #721c24; }
        .header { color: #007bff; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <h1 class="header">🚀 AlphaStock Trading System Dashboard</h1>
    
    <div id="status-container">
        Loading status...
    </div>
    
    <script>
        function updateStatus() {
            fetch('/status')
                .then(response => response.json())
                .then(data => {
                    const container = document.getElementById('status-container');
                    
                    let html = '<h2>System Status</h2>';
                    html += '<p>Last Updated: ' + new Date(data.timestamp).toLocaleString() + '</p>';
                    
                    // Application status
                    const appClass = data.application.running ? 'running' : 'stopped';
                    const appStatus = data.application.running ? '✅ Running' : '❌ Stopped';
                    html += '<div class="status ' + appClass + '">Application: ' + appStatus;
                    if (data.application.pid) html += ' (PID: ' + data.application.pid + ')';
                    html += '</div>';
                    
                    // Database status
                    const dbClass = data.database.running ? 'running' : 'stopped';
                    const dbStatus = data.database.running ? '✅ Running' : '❌ Stopped';
                    html += '<div class="status ' + dbClass + '">Database: ' + dbStatus + '</div>';
                    
                    // Recent signals
                    if (data.recent_signals.length > 0) {
                        html += '<h2>Recent Trading Signals</h2>';
                        html += '<table><tr><th>Symbol</th><th>Strategy</th><th>Action</th><th>Price</th><th>Time</th></tr>';
                        data.recent_signals.forEach(signal => {
                            html += '<tr>';
                            html += '<td>' + signal.symbol + '</td>';
                            html += '<td>' + signal.strategy + '</td>';
                            html += '<td>' + signal.signal_type + '</td>';
                            html += '<td>' + signal.entry_price + '</td>';
                            html += '<td>' + new Date(signal.timestamp).toLocaleString() + '</td>';
                            html += '</tr>';
                        });
                        html += '</table>';
                    }
                    
                    container.innerHTML = html;
                })
                .catch(error => {
                    document.getElementById('status-container').innerHTML = 
                        '<div class="status stopped">Error loading status: ' + error + '</div>';
                });
        }
        
        // Initial load and auto-refresh
        updateStatus();
        setInterval(updateStatus, 30000); // Update every 30 seconds
    </script>
</body>
</html>
        """

if __name__ == '__main__':
    server = HTTPServer(('localhost', 8080), AlphaStockHandler)
    print("🌐 AlphaStock Dashboard running at http://localhost:8080")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped")
        server.shutdown()
