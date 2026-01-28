#!/usr/bin/env python3
"""
AlphaStock Local Deployment Capacity Analysis
Evaluate system requirements for local deployment
"""

import os
import sys
import psutil
import platform
import subprocess
from pathlib import Path

def check_system_requirements():
    """Check current system capacity and requirements."""
    
    print("🖥️  SYSTEM CAPACITY ANALYSIS")
    print("=" * 40)
    
    # System Information
    system_info = {
        'os': platform.system(),
        'os_version': platform.version(),
        'architecture': platform.machine(),
        'processor': platform.processor(),
        'python_version': platform.python_version()
    }
    
    print("💻 SYSTEM INFO:")
    for key, value in system_info.items():
        print(f"  {key.replace('_', ' ').title()}: {value}")
    
    # Hardware Resources
    print(f"\n🔧 HARDWARE RESOURCES:")
    print(f"  CPU Cores: {psutil.cpu_count(logical=False)} physical, {psutil.cpu_count(logical=True)} logical")
    print(f"  CPU Usage: {psutil.cpu_percent(interval=1):.1f}%")
    
    memory = psutil.virtual_memory()
    print(f"  RAM Total: {memory.total / (1024**3):.1f} GB")
    print(f"  RAM Available: {memory.available / (1024**3):.1f} GB")
    print(f"  RAM Usage: {memory.percent:.1f}%")
    
    disk = psutil.disk_usage('/')
    print(f"  Disk Total: {disk.total / (1024**3):.1f} GB")
    print(f"  Disk Free: {disk.free / (1024**3):.1f} GB")
    print(f"  Disk Usage: {(disk.used / disk.total * 100):.1f}%")
    
    return {
        'cpu_cores': psutil.cpu_count(logical=True),
        'memory_gb': memory.total / (1024**3),
        'disk_free_gb': disk.free / (1024**3),
        'os': system_info['os']
    }

def calculate_alphastock_requirements():
    """Calculate AlphaStock system requirements."""
    
    print(f"\n📊 ALPHASTOCK REQUIREMENTS")
    print("-" * 28)
    
    requirements = {
        'minimum': {
            'cpu_cores': 2,
            'ram_gb': 4,
            'disk_gb': 10,
            'description': 'Basic MA Crossover with file storage'
        },
        'recommended': {
            'cpu_cores': 4,
            'ram_gb': 8,
            'disk_gb': 20,
            'description': 'ClickHouse + Multiple strategies + Real-time data'
        },
        'optimal': {
            'cpu_cores': 8,
            'ram_gb': 16,
            'disk_gb': 50,
            'description': 'Production-grade with full monitoring'
        }
    }
    
    for level, req in requirements.items():
        print(f"\n  {level.upper()} REQUIREMENTS:")
        print(f"    CPU: {req['cpu_cores']} cores")
        print(f"    RAM: {req['ram_gb']} GB")
        print(f"    Disk: {req['disk_gb']} GB")
        print(f"    Use Case: {req['description']}")
    
    return requirements

def evaluate_system_capacity(system_info, requirements):
    """Evaluate if system meets requirements."""
    
    print(f"\n✅ CAPACITY EVALUATION")
    print("-" * 20)
    
    levels = ['minimum', 'recommended', 'optimal']
    suitable_levels = []
    
    for level in levels:
        req = requirements[level]
        
        cpu_ok = system_info['cpu_cores'] >= req['cpu_cores']
        ram_ok = system_info['memory_gb'] >= req['ram_gb']
        disk_ok = system_info['disk_free_gb'] >= req['disk_gb']
        
        all_ok = cpu_ok and ram_ok and disk_ok
        
        print(f"\n  {level.upper()} LEVEL:")
        print(f"    CPU: {'✅' if cpu_ok else '❌'} ({system_info['cpu_cores']} >= {req['cpu_cores']})")
        print(f"    RAM: {'✅' if ram_ok else '❌'} ({system_info['memory_gb']:.1f} >= {req['ram_gb']})")
        print(f"    Disk: {'✅' if disk_ok else '❌'} ({system_info['disk_free_gb']:.1f} >= {req['disk_gb']})")
        print(f"    Overall: {'✅ SUPPORTED' if all_ok else '❌ NOT SUPPORTED'}")
        
        if all_ok:
            suitable_levels.append(level)
    
    return suitable_levels

def check_dependencies():
    """Check required dependencies."""
    
    print(f"\n🔍 DEPENDENCY CHECK")
    print("-" * 17)
    
    dependencies = {
        'docker': 'docker --version',
        'python3': 'python3 --version',
        'pip': 'pip --version',
        'git': 'git --version'
    }
    
    available = {}
    
    for dep, command in dependencies.items():
        try:
            result = subprocess.run(command.split(), capture_output=True, text=True)
            if result.returncode == 0:
                version = result.stdout.strip().split('\n')[0]
                available[dep] = version
                print(f"  ✅ {dep}: {version}")
            else:
                available[dep] = None
                print(f"  ❌ {dep}: Not found")
        except FileNotFoundError:
            available[dep] = None
            print(f"  ❌ {dep}: Not installed")
    
    return available

def estimate_resource_usage():
    """Estimate AlphaStock resource usage."""
    
    print(f"\n📈 ESTIMATED RESOURCE USAGE")
    print("-" * 26)
    
    components = {
        'Python Application': {
            'cpu': '10-20%',
            'ram': '100-200 MB',
            'description': 'Main trading logic and API calls'
        },
        'ClickHouse Database': {
            'cpu': '5-15%',
            'ram': '512 MB - 2 GB',
            'description': 'Time-series data storage and analytics'
        },
        'Real-time Data Feed': {
            'cpu': '5-10%',
            'ram': '50-100 MB',
            'description': 'WebSocket connections and data processing'
        },
        'Scheduler & Monitoring': {
            'cpu': '1-5%',
            'ram': '50-100 MB',
            'description': 'Task scheduling and system monitoring'
        }
    }
    
    total_cpu_min = 0
    total_cpu_max = 0
    total_ram_min = 0
    total_ram_max = 0
    
    for component, usage in components.items():
        print(f"\n  {component}:")
        print(f"    CPU: {usage['cpu']}")
        print(f"    RAM: {usage['ram']}")
        print(f"    Purpose: {usage['description']}")
    
    print(f"\n  TOTAL ESTIMATED USAGE:")
    print(f"    CPU: 20-50% (during market hours)")
    print(f"    RAM: 1-3 GB (with all components)")
    print(f"    Disk I/O: Moderate (data logging and ClickHouse writes)")
    print(f"    Network: Low-Medium (API calls and WebSocket feeds)")

def generate_recommendations(suitable_levels, available_deps):
    """Generate deployment recommendations."""
    
    print(f"\n💡 DEPLOYMENT RECOMMENDATIONS")
    print("=" * 28)
    
    if not suitable_levels:
        print("❌ SYSTEM NOT SUITABLE")
        print("Your system doesn't meet minimum requirements.")
        print("Consider upgrading hardware or using a cloud instance.")
        return
    
    best_level = suitable_levels[-1]  # Highest supported level
    
    print(f"✅ RECOMMENDED DEPLOYMENT LEVEL: {best_level.upper()}")
    
    if best_level == 'minimum':
        config = [
            "File-based data storage (no ClickHouse)",
            "Single MA Crossover strategy",
            "Basic logging and monitoring",
            "Paper trading mode only"
        ]
    elif best_level == 'recommended':
        config = [
            "ClickHouse database for time-series data",
            "Multiple strategies and timeframes",
            "Real-time WebSocket data feeds",
            "Comprehensive monitoring and alerts",
            "Both paper and live trading capability"
        ]
    else:  # optimal
        config = [
            "Full ClickHouse deployment with optimization",
            "Multiple strategies with backtesting",
            "Real-time analytics and reporting",
            "Advanced monitoring and performance tracking",
            "Production-grade error handling and recovery",
            "API rate optimization and caching"
        ]
    
    print(f"\nRECOMMENDED CONFIGURATION:")
    for item in config:
        print(f"  • {item}")
    
    # Dependency recommendations
    missing_deps = [dep for dep, available in available_deps.items() if not available]
    if missing_deps:
        print(f"\n🚨 INSTALL MISSING DEPENDENCIES:")
        install_commands = {
            'docker': 'brew install docker (macOS) or visit docker.com',
            'python3': 'brew install python3 or python.org',
            'pip': 'comes with python3',
            'git': 'brew install git or xcode-select --install'
        }
        
        for dep in missing_deps:
            if dep in install_commands:
                print(f"  {dep}: {install_commands[dep]}")

def main():
    """Run complete capacity analysis."""
    
    # Check system
    system_info = check_system_requirements()
    
    # Calculate requirements  
    requirements = calculate_alphastock_requirements()
    
    # Evaluate capacity
    suitable_levels = evaluate_system_capacity(system_info, requirements)
    
    # Check dependencies
    available_deps = check_dependencies()
    
    # Estimate usage
    estimate_resource_usage()
    
    # Generate recommendations
    generate_recommendations(suitable_levels, available_deps)
    
    print(f"\n📋 ANALYSIS COMPLETE")
    print("=" * 17)
    print("Ready to proceed with AlphaStock local deployment setup!")

if __name__ == "__main__":
    main()
