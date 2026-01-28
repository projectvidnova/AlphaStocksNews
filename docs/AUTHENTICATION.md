# 🔐 AlphaStock Authentication Guide

## Complete Guide to Kite Connect Authentication

> **Quick Start:** Just run `python main.py` or `python cli.py auth` - the system handles everything automatically!

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Setup](#setup)
4. [Usage](#usage)
5. [How It Works](#how-it-works)
6. [Troubleshooting](#troubleshooting)
7. [Advanced](#advanced)
8. [Security](#security)

---

## Overview

AlphaStock features **fully integrated authentication** with Kite Connect. No separate scripts needed - authentication happens seamlessly within the application.

### Key Features

✅ **Automatic Browser Launch** - Opens Kite login automatically  
✅ **Smart Token Validation** - Only prompts when needed  
✅ **Auto-Save** - Saves tokens to `.env.dev` automatically  
✅ **Seamless Re-auth** - Handles expired tokens gracefully  
✅ **Clear Guidance** - Step-by-step instructions  

---

## Quick Start

### 30-Second Setup

```bash
# 1. Add credentials to .env.dev
KITE_API_KEY=your_api_key
KITE_API_SECRET=your_api_secret

# 2. Run any command!
python main.py
# OR
python cli.py auth
```

That's it! The system will:
- 🌐 Open browser for login
- 📋 Guide you through authentication
- 💾 Save your access token
- ✅ Start trading immediately

---

## Setup

### Step 1: Get API Credentials

1. Visit [Kite Connect Developer Portal](https://kite.zerodha.com/apps)
2. Login with your Zerodha credentials
3. Create a new app or use existing
4. Note your **API Key** and **API Secret**

### Step 2: Configure `.env.dev`

```bash
# Create from template (if needed)
cp .env.example .env.dev

# Edit .env.dev and add:
KITE_API_KEY=your_api_key_here
KITE_API_SECRET=your_api_secret_here

# Optional settings:
PAPER_TRADING=true              # Safe mode (default)
PAPER_CAPITAL=100000           # Virtual capital
LOG_LEVEL=INFO                 # Logging detail
```

### Step 3: Authenticate

```bash
# Method 1: Run main application
python main.py

# Method 2: Use CLI auth command  
python cli.py auth

# Method 3: Run any CLI command
python cli.py start
python cli.py status
```

The system will automatically:
1. Open browser with Kite login page
2. Wait for you to login
3. Prompt for request_token from redirect URL
4. Exchange it for access_token
5. Save token to `.env.dev`
6. Continue with the command

---

## Usage

### Commands

#### Authenticate
```bash
# Start authentication flow
python cli.py auth
```

#### Check Status
```bash
# Validate existing token
python cli.py auth --validate-only
```

Output:
```
✅ Token is valid
   User: Rahil Tiwari
   Email: rahil@example.com
   User ID: RR3437
```

#### Run Application
```bash
# Any command auto-authenticates if needed
python main.py
python cli.py start
python cli.py status
python cli.py monitor
```

### Authentication Flow

```
┌─────────────────┐
│  Run Command    │
└────────┬────────┘
         │
         ▼
    ┌────────────┐     Valid?
    │Check Token │────────────► Continue ✅
    └────────┬───┘      YES
             │ NO
             ▼
    ┌────────────┐
    │Open Browser│◄── Automatic!
    └────────┬───┘
             │
             ▼
    ┌────────────┐
    │User Logs In│
    └────────┬───┘
             │
             ▼
    ┌────────────┐
    │Paste Token │
    └────────┬───┘
             │
             ▼
    ┌────────────┐
    │ Save Token │◄── Automatic!
    └────────┬───┘
             │
             ▼
       Continue ✅
```

### Daily Workflow

**Morning (First time each day):**
```bash
python cli.py start

# If token expired (after 24 hours):
# → Browser opens automatically
# → Login and paste token
# → System continues
```

**During the day:**
```bash
# All commands work without re-authentication
python cli.py status
python cli.py monitor
python cli.py signals
```

---

## How It Works

### Architecture

```
┌──────────────────────────────────┐
│     Application/CLI Commands      │
└───────────────┬──────────────────┘
                │
                ▼
┌──────────────────────────────────┐
│      KiteAPIClient                │
│  - initialize(auto_authenticate)  │
└───────────────┬──────────────────┘
                │
                ▼
┌──────────────────────────────────┐
│    AuthenticationManager          │
│  - ensure_authenticated()         │
│  - _validate_token()              │
│  - _interactive_authenticate()    │
│  - _save_access_token()           │
└───────────────┬──────────────────┘
                │
                ▼
┌──────────────────────────────────┐
│      SecretsManager               │
│  - get_kite_credentials()         │
│  - update_access_token()          │
└──────────────────────────────────┘
```

### Single Source of Truth

**Authentication Module** (`src/auth/auth_manager.py`):
- Manages authentication state
- Validates tokens
- Orchestrates OAuth flow
- Persists tokens

**API Client** (`src/api/kite_client.py`):
- Uses AuthenticationManager
- Handles API operations
- No duplicate auth logic

**All Other Components**:
- Reference KiteAPIClient
- No direct authentication code
- Fully centralized

### Code Example

```python
# In your code - authentication is automatic!
from src.api.kite_client import KiteAPIClient

# Initialize client
client = KiteAPIClient()
await client.initialize(auto_authenticate=True)

# If not authenticated, system will:
# 1. Open browser
# 2. Prompt for token
# 3. Save token
# 4. Continue automatically

# Use API
profile = client.get_profile()
print(f"Logged in as: {profile['user_name']}")
```

---

## Troubleshooting

### Browser Doesn't Open?

**Symptom:** Browser doesn't launch automatically

**Solution:** URL is shown in terminal - copy and open manually
```
⚠️ Could not open browser automatically.
Please manually open this URL:
https://kite.zerodha.com/connect/login?api_key=...
```

### "Request token expired"

**Symptom:** Error after pasting token

**Cause:** Request tokens expire in ~2 minutes

**Solution:** Run auth again and paste quickly:
```bash
python cli.py auth
```

### "Invalid access token"

**Symptom:** Authentication fails on startup

**Cause:** Access tokens expire after 24 hours

**Solution:** System will auto re-authenticate:
```bash
python cli.py start
# Browser opens → Login → Paste token → Done!
```

### Missing API Credentials

**Symptom:** "API key not found"

**Solution:** Update `.env.dev`:
```bash
KITE_API_KEY=your_api_key
KITE_API_SECRET=your_api_secret
```

Get credentials from: https://kite.zerodha.com/apps

### Permission Denied

**Symptom:** Can't save token to `.env.dev`

**Solution (Windows):**
```powershell
icacls .env.dev /grant:r "$($env:USERNAME):(R,W)"
```

**Solution (Linux/Mac):**
```bash
chmod 600 .env.dev
```

---

## Advanced

### Programmatic Usage

```python
from src.auth import get_auth_manager

# Get authentication manager
auth_manager = get_auth_manager()

# Interactive authentication (opens browser)
if await auth_manager.ensure_authenticated(interactive=True):
    profile = auth_manager.get_profile()
    print(f"Logged in as: {profile['user_name']}")

# Non-interactive (just validates)
if await auth_manager.ensure_authenticated(interactive=False):
    print("Already authenticated")
else:
    print("Need to authenticate")
```

### Custom Auth Flow

```python
from src.auth import AuthenticationManager

# Create auth manager
auth_manager = AuthenticationManager()

# Perform authentication
authenticated = await auth_manager.ensure_authenticated(interactive=True)

if authenticated:
    # Get profile
    profile = auth_manager.get_profile()
    
    # Use authenticated session
    # ...
    
    # Invalidate when done
    auth_manager.invalidate_token()
```

### Session Expiry Hook

```python
from src.api.kite_client import KiteAPIClient

client = KiteAPIClient()
await client.initialize()

# Set custom handler for token expiry
def on_session_expired(exc):
    print(f"Session expired: {exc}")
    # Trigger re-authentication
    asyncio.create_task(client.initialize(auto_authenticate=True))

client.kite.set_session_expiry_hook(on_session_expired)
```

---

## Security

### Best Practices

✅ **Do:**
- Keep `.env.dev` in `.gitignore` (already configured)
- Use paper trading mode for testing: `PAPER_TRADING=true`
- Never commit API secrets to version control
- Review app permissions on Kite portal regularly
- Regenerate credentials if compromised

❌ **Don't:**
- Share your `.env.dev` file
- Commit access tokens to git
- Use live trading without thorough testing
- Store credentials in code
- Share your Kite Connect API secret

### Token Management

**Access Token Lifecycle:**
- Expires after 24 hours (Kite policy)
- System validates on startup
- Auto re-authenticates when expired
- Saved securely in `.env.dev`

**Security Features:**
- Tokens stored locally only
- No transmission except to Kite API
- Environment-based configuration
- Secure file permissions

### Environment Variables

**Required:**
```bash
KITE_API_KEY=your_api_key          # From Kite portal
KITE_API_SECRET=your_api_secret    # From Kite portal  
```

**Auto-generated:**
```bash
KITE_ACCESS_TOKEN=auto_saved       # After authentication
```

**Optional:**
```bash
PAPER_TRADING=true                 # Enable paper trading (default)
PAPER_CAPITAL=100000              # Initial capital
LOG_LEVEL=INFO                    # Logging level
DEBUG_MODE=false                  # Debug mode
```

---

## Summary

### What Makes It Special

✨ **Fully Integrated** - No separate scripts  
✨ **Automatic** - Browser launches automatically  
✨ **Smart** - Validates before prompting  
✨ **Persistent** - Saves tokens automatically  
✨ **Seamless** - Re-authenticates when needed  
✨ **Simple** - Just one command!  

### Quick Reference

| Task | Command |
|------|---------|
| **Authenticate** | `python cli.py auth` |
| **Check Status** | `python cli.py auth --validate-only` |
| **Start Trading** | `python main.py` |
| **Run CLI** | `python cli.py start` |
| **Monitor System** | `python cli.py monitor` |

### Architecture

```
src/auth/auth_manager.py        ← Single source of truth
       ↓
src/api/kite_client.py          ← API operations  
       ↓
Application Components           ← Use KiteAPIClient
```

### Support

- **Documentation**: This file
- **Test Script**: `python test_auth.py`
- **Logs**: Check `logs/` directory
- **Issues**: Review error messages in terminal

---

**Ready to trade?**

```bash
# 1. Set up credentials
echo "KITE_API_KEY=your_key" > .env.dev
echo "KITE_API_SECRET=your_secret" >> .env.dev

# 2. Run!
python main.py

# That's it! 🚀
```

---

*Last Updated: October 6, 2025*  
*Version: 2.0 (Consolidated)*
