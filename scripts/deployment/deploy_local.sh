#!/bin/bash
# AlphaStock Local Deployment Script
# Complete deployment automation for local machine

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="alphastock"
PROJECT_DIR="/Users/adithyasaladi/Personal/AlphaStock"
VENV_NAME=".venv"
CLICKHOUSE_CONTAINER="alphastock-clickhouse"
LOG_DIR="logs"

print_header() {
    echo -e "${BLUE}🚀 ALPHASTOCK LOCAL DEPLOYMENT${NC}"
    echo -e "${BLUE}================================${NC}"
    echo ""
}

print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
    exit 1
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

check_prerequisites() {
    print_info "Checking prerequisites..."
    
    # Check if running on macOS
    if [[ "$OSTYPE" != "darwin"* ]]; then
        print_warning "This script is optimized for macOS. Adjustments may be needed for other OS."
    fi
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is required but not installed. Please install Docker Desktop."
    fi
    
    # Check Docker is running
    if ! docker info &> /dev/null; then
        print_error "Docker is installed but not running. Please start Docker Desktop."
    fi
    
    # Check Python 3
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is required but not installed."
    fi
    
    # Check Git
    if ! command -v git &> /dev/null; then
        print_error "Git is required but not installed."
    fi
    
    print_status "All prerequisites satisfied"
}

setup_python_environment() {
    print_info "Setting up Python environment..."
    
    cd "$PROJECT_DIR"
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "$VENV_NAME" ]; then
        python3 -m venv "$VENV_NAME"
        print_status "Virtual environment created"
    else
        print_status "Virtual environment already exists"
    fi
    
    # Activate virtual environment
    source "$VENV_NAME/bin/activate"
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install requirements
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
        print_status "Python dependencies installed"
    else
        print_warning "requirements.txt not found, skipping dependency installation"
    fi
}

setup_directories() {
    print_info "Setting up directories..."
    
    cd "$PROJECT_DIR"
    
    # Create necessary directories
    mkdir -p "$LOG_DIR"
    mkdir -p "data/historical"
    mkdir -p "data/signals"
    mkdir -p "config"
    
    print_status "Directories created"
}

setup_clickhouse() {
    print_info "Setting up ClickHouse database..."
    
    cd "$PROJECT_DIR"
    
    # Check if ClickHouse container already exists
    if docker ps -a --format "table {{.Names}}" | grep -q "^${CLICKHOUSE_CONTAINER}$"; then
        print_info "ClickHouse container already exists, starting it..."
        docker start "$CLICKHOUSE_CONTAINER" || true
    else
        # Run ClickHouse setup script
        if [ -f "scripts/database/setup_clickhouse_docker.sh" ]; then
            chmod +x scripts/database/setup_clickhouse_docker.sh
            ./scripts/database/setup_clickhouse_docker.sh
            print_status "ClickHouse database setup complete"
        else
            print_warning "ClickHouse setup script not found, skipping database setup"
        fi
    fi
    
    # Wait for ClickHouse to be ready
    print_info "Waiting for ClickHouse to be ready..."
    for i in {1..30}; do
        if docker exec "$CLICKHOUSE_CONTAINER" clickhouse-client --query "SELECT 1" &> /dev/null; then
            print_status "ClickHouse is ready"
            break
        fi
        sleep 2
        if [ $i -eq 30 ]; then
            print_warning "ClickHouse may not be fully ready, but continuing..."
        fi
    done
}

setup_configuration() {
    print_info "Setting up configuration..."
    
    cd "$PROJECT_DIR"
    
    # Check for environment file
    if [ ! -f ".env.dev" ]; then
        print_warning ".env.dev not found. Please create it with your API credentials."
        print_info "Example .env.dev content:"
        echo "KITE_API_KEY=your_api_key_here"
        echo "KITE_API_SECRET=your_api_secret_here"
        echo "KITE_ACCESS_TOKEN=your_access_token_here"
        echo ""
    else
        print_status "Environment configuration found"
    fi
    
    # Check for database config
    if [ -f "config/database.json" ]; then
        print_status "Database configuration found"
    else
        print_info "Creating default database configuration..."
        cat > config/database.json << 'EOF'
{
    "clickhouse": {
        "host": "localhost",
        "port": 9000,
        "database": "alphastock",
        "user": "default",
        "password": ""
    },
    "redis": {
        "host": "localhost",
        "port": 6379,
        "database": 0
    }
}
EOF
        print_status "Default database configuration created"
    fi
}

create_systemd_service() {
    print_info "Creating system service files..."
    
    cd "$PROJECT_DIR"
    
    # Create launchd plist for macOS (equivalent to systemd)
    cat > "com.alphastock.scheduler.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.alphastock.scheduler</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PROJECT_DIR/$VENV_NAME/bin/python</string>
        <string>$PROJECT_DIR/scheduler.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/logs/scheduler.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/logs/scheduler_error.log</string>
</dict>
</plist>
EOF
    
    print_status "System service configuration created"
}

create_management_scripts() {
    print_info "Creating management scripts..."
    
    cd "$PROJECT_DIR"
    
    # Create start script
    cat > "start_alphastock.sh" << 'EOF'
#!/bin/bash
# Start AlphaStock Trading System

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🚀 Starting AlphaStock Trading System${NC}"
echo "======================================"

# Start ClickHouse if not running
if ! docker ps | grep -q "alphastock-clickhouse"; then
    echo "Starting ClickHouse database..."
    docker start alphastock-clickhouse
    sleep 5
fi

# Activate Python environment
source .venv/bin/activate

# Start the scheduler (this will start the main application)
echo -e "${GREEN}✅ Starting AlphaStock Scheduler...${NC}"
nohup python scheduler.py > logs/alphastock.log 2>&1 &
echo $! > alphastock.pid

echo -e "${GREEN}✅ AlphaStock Trading System Started${NC}"
echo "PID: $(cat alphastock.pid)"
echo "Logs: tail -f logs/alphastock.log"
echo "Stop with: ./stop_alphastock.sh"
EOF
    
    # Create stop script
    cat > "stop_alphastock.sh" << 'EOF'
#!/bin/bash
# Stop AlphaStock Trading System

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${RED}🛑 Stopping AlphaStock Trading System${NC}"
echo "====================================="

# Stop the main application
if [ -f "alphastock.pid" ]; then
    PID=$(cat alphastock.pid)
    if ps -p $PID > /dev/null 2>&1; then
        kill $PID
        echo -e "${GREEN}✅ AlphaStock process stopped (PID: $PID)${NC}"
    else
        echo "Process not running"
    fi
    rm -f alphastock.pid
else
    echo "PID file not found, trying to find process..."
    pkill -f "python scheduler.py" && echo -e "${GREEN}✅ AlphaStock processes stopped${NC}" || echo "No processes found"
fi

# Optionally stop ClickHouse (uncomment if you want to stop it)
# docker stop alphastock-clickhouse

echo -e "${GREEN}✅ AlphaStock Trading System Stopped${NC}"
EOF
    
    # Create status script
    cat > "status_alphastock.sh" << 'EOF'
#!/bin/bash
# Check AlphaStock Trading System Status

BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}📊 AlphaStock Trading System Status${NC}"
echo "===================================="

# Check main application
if [ -f "alphastock.pid" ]; then
    PID=$(cat alphastock.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo -e "Main Application: ${GREEN}✅ Running (PID: $PID)${NC}"
    else
        echo -e "Main Application: ${RED}❌ Not Running${NC}"
    fi
else
    echo -e "Main Application: ${RED}❌ PID file not found${NC}"
fi

# Check ClickHouse
if docker ps | grep -q "alphastock-clickhouse"; then
    echo -e "ClickHouse Database: ${GREEN}✅ Running${NC}"
    # Test connection
    if docker exec alphastock-clickhouse clickhouse-client --query "SELECT 1" &> /dev/null; then
        echo -e "Database Connection: ${GREEN}✅ OK${NC}"
    else
        echo -e "Database Connection: ${RED}❌ Failed${NC}"
    fi
else
    echo -e "ClickHouse Database: ${RED}❌ Not Running${NC}"
fi

# Check logs
echo ""
echo "Recent Log Entries:"
if [ -f "logs/alphastock.log" ]; then
    tail -5 logs/alphastock.log
else
    echo "No log file found"
fi

echo ""
echo "Commands:"
echo "  Start:  ./start_alphastock.sh"
echo "  Stop:   ./stop_alphastock.sh"
echo "  Logs:   tail -f logs/alphastock.log"
EOF
    
    # Make scripts executable
    chmod +x start_alphastock.sh
    chmod +x stop_alphastock.sh  
    chmod +x status_alphastock.sh
    
    print_status "Management scripts created"
}

create_monitoring_dashboard() {
    print_info "Creating monitoring dashboard..."
    
    cd "$PROJECT_DIR"
    
    cat > "dashboard.py" << 'EOF'
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
            'timestamp': datetime.now().isoformat(),
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
EOF
    
    chmod +x dashboard.py
    print_status "Monitoring dashboard created"
}

run_deployment() {
    print_header
    
    print_info "Starting AlphaStock local deployment..."
    print_info "Project Directory: $PROJECT_DIR"
    echo ""
    
    # Run deployment steps
    check_prerequisites
    setup_directories
    setup_python_environment
    setup_clickhouse
    setup_configuration
    create_systemd_service
    create_management_scripts
    create_monitoring_dashboard
    
    echo ""
    print_status "AlphaStock deployment completed successfully!"
    echo ""
    
    print_info "Next Steps:"
    echo "1. Configure your API credentials in .env.dev"
    echo "2. Start the system: ./start_alphastock.sh" 
    echo "3. Check status: ./status_alphastock.sh"
    echo "4. Monitor dashboard: python dashboard.py"
    echo "5. View logs: tail -f logs/alphastock.log"
    echo ""
    
    print_info "Management Commands:"
    echo "  Start:  ./start_alphastock.sh"
    echo "  Stop:   ./stop_alphastock.sh"
    echo "  Status: ./status_alphastock.sh"
    echo "  Dashboard: python dashboard.py (http://localhost:8080)"
    echo ""
}

# Run deployment if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    run_deployment
fi
