# AlphaStocks Documentation

Complete documentation for the AlphaStocks Algorithmic T### Understanding the System
- **⭐ System Architecture**: [Low Level Design](LOW_LEVEL_DESIGN.md) - **START HERE** - Complete system documentation
- **Signal Storage**: [Where to Find Signals](WHERE_TO_FIND_SIGNALS.md) - How to access generated signals
- **Application Modules**: [Project Structure](PROJECT_STRUCTURE.md)
- **Trading Logic**: [Strategy Implementations](strategy_implementations.md)
- **Options Features**: [Options Trading Guide](OPTIONS_TRADING_GUIDE.md)
- **Database Queries**: [Database Queries Guide](DATABASE_QUERIES.md)
- **Complete Trading Flow**: [End-to-End Trading Flow](COMPLETE_TRADING_FLOW.md)
- **Real-Time Data**: [Real-Time Data Fetching](REALTIME_DATA_FETCHING.md)
- **Runners System**: [Runners Architecture](RUNNERS_ARCHITECTURE.md)
- **Data Pipeline**: [Historical Data Pipeline](HISTORICAL_DATA_PIPELINE_IMPLEMENTATION.md) - How strategies get historical + real-time data
- **Data Flow Verification**: ✅ [Data Flow Verification](DATA_FLOW_VERIFICATION.md) - Proof that strategies receive merged historical + live data
- **Event-Driven System**: 🔄 [Event-Driven Architecture](EVENT_DRIVEN_ARCHITECTURE.md) - Modern pub/sub architectureem.

---

> 📘 **⭐ ESSENTIAL READING**  
> **[Low Level Design](LOW_LEVEL_DESIGN.md)** - **Complete System Architecture Documentation**  
> Comprehensive guide covering the entire system from data collection to trade execution:
> - Complete data flow diagrams (Historical + Realtime → Strategy → Signal → Options)
> - All 14 component details with attributes and methods
> - Event-driven architecture with lock-free concurrency
> - Database schema (6 tables with SQL queries)
> - Three execution modes with detailed flows
> - Signal storage locations and monitoring guides
> - Troubleshooting and deployment checklists

---

## 📖 Quick Navigation

### 🚀 Getting Started
- **[Quick Start Guide](QUICK_START.md)** - Setup and run in 5 minutes
- **[Authentication Setup](AUTHENTICATION.md)** - Configure Zerodha Kite Connect
- **[Credentials Configuration](SETUP_CREDENTIALS.md)** - API keys and environment setup

### 🏗️ System Architecture & Design ⭐ **ESSENTIAL**
- **[Low Level Design](LOW_LEVEL_DESIGN.md)** - ⭐ **Complete system architecture documentation**
- **[Where to Find Signals](WHERE_TO_FIND_SIGNALS.md)** - Signal storage locations and queries
- **[Market Hours Protection](MARKET_HOURS_PROTECTION.md)** - 🛡️ **Critical: Prevents data corruption after 3:30 PM**
- **[Event-Driven Architecture](EVENT_DRIVEN_ARCHITECTURE.md)** - EventBus and pub-sub pattern
- **[Lock-Free Architecture](LOCK_FREE_ARCHITECTURE.md)** - Concurrency design and thread safety
- **[Event-Driven Summary](EVENT_DRIVEN_SUMMARY.md)** - Quick overview of event system

#### Detailed Low-Level Design (Multi-Part)
For in-depth study, see the detailed 6-part documentation:
- [Part 1: System Overview & Data Collection](LOW_LEVEL_DESIGN_PART1.md)
- [Part 2: Signal Processing & Execution](LOW_LEVEL_DESIGN_PART2.md)
- [Part 3: Execution Modes & Core Classes](LOW_LEVEL_DESIGN_PART3.md)
- [Part 4: Additional Components & Sequences](LOW_LEVEL_DESIGN_PART4.md)
- [Part 5: Final Components & Database Schema](LOW_LEVEL_DESIGN_PART5.md)
- [Part 6: Summary & Quick Reference](LOW_LEVEL_DESIGN_PART6.md)

### 📚 Application Modules
- **[Project Structure](PROJECT_STRUCTURE.md)** - Application architecture and modules
- **[Trading Strategies](strategy_implementations.md)** - Available trading strategies
- **[Options Trading](OPTIONS_TRADING_GUIDE.md)** - Options trading features
- **[Database Queries](DATABASE_QUERIES.md)** - How to query stock data from ClickHouse
- **[Complete Trading Flow](COMPLETE_TRADING_FLOW.md)** - End-to-end flow from data fetch to order placement
- **[Real-Time Data Fetching](REALTIME_DATA_FETCHING.md)** - How market data is fetched (Polling vs WebSocket)
- **[Runners Architecture](RUNNERS_ARCHITECTURE.md)** - Specialized runners for different asset types (Index, Equity, Options, Futures)

### 📊 Data Pipeline & Historical Data
- **[Historical Data Pipeline Implementation](HISTORICAL_DATA_PIPELINE_IMPLEMENTATION.md)** - Complete modular data pipeline architecture
- **[Data Flow Verification](DATA_FLOW_VERIFICATION.md)** - ✅ How strategies receive merged historical + live data
- **[Quick Start: Data Pipeline](QUICK_START_DATA_PIPELINE.md)** - Quick reference for data pipeline components

### 🎯 Options Trading Integration
- **[Options Trading Complete Implementation](OPTIONS_TRADING_COMPLETE.md)** - ✅ All 5 modules integrated with paper trading support

### 🔄 Event-Driven Architecture (Recommended)
- **[Event-Driven Summary](EVENT_DRIVEN_SUMMARY.md)** - � **START HERE** - Quick overview and benefits
- **[Event-Driven Architecture](EVENT_DRIVEN_ARCHITECTURE.md)** - � Complete architecture guide with diagrams
- **[Quick Start: Event-Driven](QUICK_START_EVENT_DRIVEN.md)** - ⚡ Step-by-step integration guide

### 🚀 Deployment
- **[Production Deployment](PRODUCTION_DEPLOYMENT.md)** - Deploy to production
- **[Deployment Guide](DEPLOYMENT_GUIDE.md)** - General deployment instructions
- **[Local Setup](LOCAL_DEPLOYMENT_COMPLETE.md)** - Local development environment

### 🤖 Advanced Features
- **[AI Framework](AI_FRAMEWORK_COMPLETE.md)** - AI/ML integration
- **[AI Solution Architecture](AI_SOLUTION_CLEAN.md)** - AI system design

### 🔧 Technical Documentation
- **[SDK vs API Analysis](SDK_VS_API_ANALYSIS.md)** - Technical architecture decisions
- **[Integrated Authentication](INTEGRATED_AUTH.md)** - Authentication system internals

---

## 📋 Documentation by Task

### First-Time Setup
1. Read [Quick Start Guide](QUICK_START.md)
2. Configure [Credentials](SETUP_CREDENTIALS.md)
3. Setup [Authentication](AUTHENTICATION.md)
4. Review [Project Structure](PROJECT_STRUCTURE.md)

### Understanding the System
- **Application Modules**: [Project Structure](PROJECT_STRUCTURE.md)
- **Trading Logic**: [Strategy Implementations](strategy_implementations.md)
- **Options Features**: [Options Trading Guide](OPTIONS_TRADING_GUIDE.md)
- **Database Queries**: [Database Queries Guide](DATABASE_QUERIES.md)
- **Complete Trading Flow**: [End-to-End Trading Flow](COMPLETE_TRADING_FLOW.md)
- **Real-Time Data**: [Real-Time Data Fetching](REALTIME_DATA_FETCHING.md)
- **Runners System**: [Runners Architecture](RUNNERS_ARCHITECTURE.md)
- **Data Pipeline**: [Historical Data Pipeline](HISTORICAL_DATA_PIPELINE_IMPLEMENTATION.md) - How strategies get historical + real-time data
- **Data Flow Verification**: ✅ [Data Flow Verification](DATA_FLOW_VERIFICATION.md) - Proof that strategies receive merged historical + live data
- **Event-Driven System**: � [Event-Driven Architecture](EVENT_DRIVEN_ARCHITECTURE.md) - Modern pub/sub architecture

### Deployment
- **Local Testing**: [Local Setup](LOCAL_DEPLOYMENT_COMPLETE.md)
- **Production**: [Production Deployment](PRODUCTION_DEPLOYMENT.md)

### Advanced Topics
- **Event-Driven**: 🚀 [Event-Driven Summary](EVENT_DRIVEN_SUMMARY.md) - Start here for modern architecture
- **AI/ML**: [AI Framework](AI_FRAMEWORK_COMPLETE.md)
- **Architecture**: [SDK vs API](SDK_VS_API_ANALYSIS.md)

---

## 🎯 By User Role

### Traders
Focus on these documents:
1. [Quick Start](QUICK_START.md) - Daily workflow
2. [Authentication](AUTHENTICATION.md) - Login setup
3. [Trading Strategies](strategy_implementations.md) - Available strategies
4. [Options Trading](OPTIONS_TRADING_GUIDE.md) - Options features

### Developers
Focus on these documents:
1. ⭐ [Low Level Design](LOW_LEVEL_DESIGN.md) - **START HERE** - Complete system architecture
2. [Where to Find Signals](WHERE_TO_FIND_SIGNALS.md) - Signal storage and queries
3. [Event-Driven Architecture](EVENT_DRIVEN_ARCHITECTURE.md) - EventBus and pub-sub pattern
4. [Lock-Free Architecture](LOCK_FREE_ARCHITECTURE.md) - Concurrency design
5. [Project Structure](PROJECT_STRUCTURE.md) - Code organization
6. [Historical Data Pipeline](HISTORICAL_DATA_PIPELINE_IMPLEMENTATION.md) - Data pipeline architecture
7. [SDK vs API](SDK_VS_API_ANALYSIS.md) - Architecture decisions
8. [AI Framework](AI_FRAMEWORK_COMPLETE.md) - AI capabilities

### DevOps
Focus on these documents:
1. [Production Deployment](PRODUCTION_DEPLOYMENT.md) - Production setup
2. [Deployment Guide](DEPLOYMENT_GUIDE.md) - Deployment procedures
3. [Local Setup](LOCAL_DEPLOYMENT_COMPLETE.md) - Development environment

---

## 📞 Support

- **Main README**: [../README.md](../README.md)
- **Issues**: [GitHub Issues](https://github.com/projectvidnova/AlphaStocks/issues)
- **Kite Connect Docs**: https://kite.trade/docs/connect/v3/

---

## ⭐ Recent Updates

### Complete Low-Level Design Documentation (October 2025) 📘 **NEW**

**Major Documentation Release**: Comprehensive system architecture documentation covering every aspect of the AlphaStocks trading system.

**What's Included:**
- ✅ Complete end-to-end data flow (Historical + Realtime → Strategy → Signal → Options)
- ✅ All 14 components with detailed class structures, attributes, and methods
- ✅ Event-driven architecture with lock-free concurrency patterns
- ✅ Complete database schema (6 tables) with CREATE statements and query examples
- ✅ Three execution modes with detailed flows (Logging Only → Paper Trading → Live Trading)
- ✅ Signal storage locations and access patterns
- ✅ Position monitoring background tasks
- ✅ Troubleshooting guide with common issues and solutions
- ✅ Deployment checklist (3-phase approach)
- ✅ Configuration reference with all flags and parameters

**Documentation:**
- **[Low Level Design](LOW_LEVEL_DESIGN.md)** - ⭐ **Main consolidated document**
- Multi-part detailed documentation: [PART1](LOW_LEVEL_DESIGN_PART1.md) | [PART2](LOW_LEVEL_DESIGN_PART2.md) | [PART3](LOW_LEVEL_DESIGN_PART3.md) | [PART4](LOW_LEVEL_DESIGN_PART4.md) | [PART5](LOW_LEVEL_DESIGN_PART5.md) | [PART6](LOW_LEVEL_DESIGN_PART6.md)

**Key Features:**
- 📊 ASCII flow diagrams showing complete data flow
- 🗄️ Database schema with idempotency and thread-safety patterns
- 🔄 EventBus publish-subscribe architecture
- 🔒 Lock-free concurrency design (no mutexes, no deadlocks)
- 🛡️ Safe deployment progression (logging → paper → live)

### Event-Driven Architecture (October 2025) 🚀

**Major Enhancement**: Implemented complete event-driven architecture using publish-subscribe pattern.

**What Changed:**
- ✅ Strategies emit signals as events (no direct coupling)
- ✅ Options executor subscribes automatically (catches all signals)
- ✅ Position manager publishes lifecycle events
- ✅ Easy to add notifications, analytics, or any feature by subscribing
- ✅ Complete observability with event history and statistics

**New Components:**
1. **EventBus** - Central pub/sub hub with priority queue (~400 lines)
2. **EventDrivenSignalManager** - Publishes signal events (~400 lines)
3. **EventDrivenOptionsExecutor** - Subscribes to signals (~450 lines)
4. **11 Event Types** - Signal, Position, Trade, Order events

**Documentation:**
- **[Event-Driven Summary](EVENT_DRIVEN_SUMMARY.md)** - 🚀 **START HERE** - Quick overview
- **[Event-Driven Architecture](EVENT_DRIVEN_ARCHITECTURE.md)** - Complete guide with diagrams
- **[Quick Start: Event-Driven](QUICK_START_EVENT_DRIVEN.md)** - Step-by-step integration

**Benefits:**
- 🔗 Zero coupling between components
- 📈 Easy to scale and extend
- 🧪 Testable in isolation
- 👁️ Full observability
- 🔄 Flexible event routing

### Historical Data Pipeline (October 2025)

**Major Enhancement**: Implemented complete modular data pipeline providing strategies with proper historical context.

**Key Features:**
- ✅ Strategies analyze 20-60 days of data (3,600-10,800x more depth)
- ✅ Smart caching with 80-95% hit rate
- ✅ Seamless merge of historical + live data

**Documentation:**
- **[Historical Data Pipeline](HISTORICAL_DATA_PIPELINE_IMPLEMENTATION.md)** - Complete guide
- **[Data Flow Verification](DATA_FLOW_VERIFICATION.md)** - ✅ Verification proof

---

**Note**: This documentation focuses on application features and usage. For development history, see `archive/development_history/`.
