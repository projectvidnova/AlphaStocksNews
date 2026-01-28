# 🔐 Integrated Authentication Guide

## Overview

AlphaStock now features **integrated authentication** that handles the Kite Connect OAuth flow seamlessly within the application. No need to run separate scripts!

## Quick Start

### 1. Set Up Credentials (One-Time)

Create or update your `.env.dev` file with your Kite Connect credentials:

```bash
# Copy from template
cp .env.example .env.dev

# Edit .env.dev and add:
KITE_API_KEY=your_api_key_here
KITE_API_SECRET=your_api_secret_here
```

Get your API credentials from: https://kite.zerodha.com/apps

### 2. Authenticate

Simply run any command - the system will automatically guide you through authentication if needed:

```bash
# Option A: Run the main application
python main.py

# Option B: Use the CLI auth command
python cli.py auth

# Option C: Validate existing token
python cli.py auth --validate-only
```

## How It Works

### Automatic Authentication Flow

1. **Application starts** → Checks for valid access token
2. **Token missing/invalid** → Opens browser for login automatically
3. **You login** → Copy request_token from redirect URL
4. **Paste token** → System exchanges it for access token
5. **Token saved** → Automatically saved to .env.dev
6. **Ready to trade!** → Application continues normally

### Smart Features

✅ **Automatic Browser Launch** - Opens Kite login page automatically  
✅ **Token Validation** - Checks existing tokens before prompting  
✅ **Auto-Save** - Saves access token to .env.dev automatically  
✅ **Silent Re-auth** - Prompts only when needed  
✅ **Non-Blocking** - Uses async/await for seamless operation  

## Usage Examples

### Example 1: First Time Setup

```bash
# Step 1: Create .env.dev with API credentials
echo "KITE_API_KEY=your_key" > .env.dev
echo "KITE_API_SECRET=your_secret" >> .env.dev

# Step 2: Run any command
python cli.py status

# Output:
# 🔑 KITE CONNECT AUTHENTICATION REQUIRED
# ========================================
# 
# 📋 Authentication Steps:
# 1. Your browser will open with the Kite login page
# 2. Login with your Zerodha credentials
# 3. After successful login, copy the 'request_token' from the URL
# 4. Paste it back here when prompted
#
# 🌐 Opening browser for authentication...
# [Browser opens automatically]
#
# After login, the URL will look like:
# https://127.0.0.1:8080/?request_token=XXXXXX&action=login&status=success
#
# 🔑 Paste the request_token here: [you paste here]
#
# 🔄 Generating session...
#
# ====================================
# ✅ AUTHENTICATION SUCCESSFUL!
# ====================================
# ✓ User: Your Name
# ✓ User ID: AB1234
# ✓ Email: your@email.com
# ✓ Access token saved to .env.dev
# ====================================
```

### Example 2: Daily Use (Token Expired)

```bash
# Just run the command - auto-reauth if token expired
python cli.py start

# If token expired:
# ⚠️ Access token expired. Re-authenticating...
# [Opens browser automatically]
# [You login and paste token]
# ✅ Authentication successful!
# 🚀 Starting trading system...
```

### Example 3: Check Authentication Status

```bash
# Validate without re-authenticating
python cli.py auth --validate-only

# Output:
# ✅ Token is valid
#    User: Your Name
#    Email: your@email.com
#    User ID: AB1234
```

### Example 4: Manual Authentication

```bash
# Force re-authentication
python cli.py auth

# This will:
# 1. Open browser for login
# 2. Guide you through token exchange
# 3. Save new access token
# 4. Confirm success
```

## CLI Commands

### Authentication Commands

```bash
# Authenticate (opens browser)
python cli.py auth

# Check if already authenticated
python cli.py auth --validate-only

# Any other command auto-authenticates if needed
python cli.py status
python cli.py start
python cli.py monitor
```

## Programmatic Usage

### In Your Code

```python
from src.auth import get_auth_manager

# Get authentication manager
auth_manager = get_auth_manager()

# Ensure authenticated (will prompt if needed)
if await auth_manager.ensure_authenticated(interactive=True):
    print("Ready to use Kite API!")
    profile = auth_manager.get_profile()
    print(f"Logged in as: {profile['user_name']}")
else:
    print("Authentication failed")

# Non-interactive mode (won't prompt, just validates)
if await auth_manager.ensure_authenticated(interactive=False):
    print("Already authenticated")
else:
    print("Need to authenticate")
```

### Using KiteAPIClient

```python
from src.api.kite_client import KiteAPIClient

# Initialize client (auto-authenticates if needed)
client = KiteAPIClient()
await client.initialize(auto_authenticate=True)  # Opens browser if needed

# Or skip auto-auth
await client.initialize(auto_authenticate=False)  # Fails if not authenticated
```

## Configuration

### Environment Variables

Required:
```bash
KITE_API_KEY=your_api_key          # From Kite Connect developer portal
KITE_API_SECRET=your_api_secret    # From Kite Connect developer portal
```

Auto-generated:
```bash
KITE_ACCESS_TOKEN=auto_generated   # Automatically saved after authentication
```

Optional:
```bash
PAPER_TRADING=true                 # Enable paper trading (default: true)
PAPER_CAPITAL=100000               # Initial capital for paper trading
LOG_LEVEL=INFO                     # Logging level
DEBUG_MODE=false                   # Debug mode
```

## Token Management

### Token Lifecycle

- **Access tokens expire after 24 hours** (Kite Connect policy)
- System automatically validates tokens on startup
- Prompts for re-authentication when token expires
- New tokens are automatically saved

### Daily Workflow

```bash
# Morning (first time of the day)
python cli.py start

# If token expired:
# [Browser opens] → Login → Paste token → Done!

# Rest of the day - no re-authentication needed
python cli.py status
python cli.py monitor
python cli.py signals
```

## Troubleshooting

### Browser Doesn't Open

**Solution:** Manually open the URL shown in the terminal

```bash
# Copy the URL from terminal:
# Please manually open this URL:
# https://kite.zerodha.com/connect/login?api_key=...

# Open in browser, login, and paste token when prompted
```

### "request_token expired"

**Cause:** Request tokens are valid for only ~2 minutes

**Solution:** Start the authentication process again:
```bash
python cli.py auth
```

### "Invalid access token"

**Cause:** Token has expired (after 24 hours)

**Solution:** Just run any command - system will re-authenticate:
```bash
python cli.py status  # Auto re-authenticates if needed
```

### Missing API Credentials

**Error:** `API key not found`

**Solution:** Update your `.env.dev` file:
```bash
# Add these lines to .env.dev
KITE_API_KEY=your_api_key_here
KITE_API_SECRET=your_api_secret_here
```

Get credentials from: https://kite.zerodha.com/apps

### Permission Denied on .env.dev

**Cause:** File permissions issue

**Solution:**
```bash
# Windows (PowerShell)
icacls .env.dev /grant:r "$($env:USERNAME):(R,W)"

# Linux/Mac
chmod 600 .env.dev
```

## Security Best Practices

### ✅ Do's

- Keep `.env.dev` in `.gitignore` (already configured)
- Use paper trading mode for testing (`PAPER_TRADING=true`)
- Never share your API secret
- Regenerate credentials if compromised
- Review app permissions on Kite Connect portal

### ❌ Don'ts

- Don't commit `.env.dev` to version control
- Don't share access tokens
- Don't use live trading without thorough testing
- Don't store credentials in code
- Don't share your Kite Connect API secret

## Advanced Features

### Session Expiry Hook

```python
from src.api.kite_client import KiteAPIClient

client = KiteAPIClient()

# Set a custom session expiry handler
def on_session_expired(exc):
    print(f"Session expired: {exc}")
    # Auto re-authenticate
    asyncio.create_task(client.initialize(auto_authenticate=True))

client.kite.set_session_expiry_hook(on_session_expired)
```

### Custom Authentication Flow

```python
from src.auth import AuthenticationManager

# Create custom auth manager
auth_manager = AuthenticationManager()

# Perform authentication
authenticated = await auth_manager.ensure_authenticated(interactive=True)

if authenticated:
    # Get profile
    profile = auth_manager.get_profile()
    print(f"Welcome {profile['user_name']}!")
    
    # Invalidate token when done
    auth_manager.invalidate_token()
```

## Migration from Old System

### Before (Manual Scripts)

```bash
# Old way - multiple steps
python scripts/utilities/get_auth_url.py   # Get URL
# Open browser manually
# Copy token
python scripts/utilities/auth_helper.py    # Paste token
python main.py                              # Start app
```

### After (Integrated)

```bash
# New way - single command!
python main.py
# Everything handled automatically
```

### Backward Compatibility

Old scripts still work but are no longer needed:
- `scripts/utilities/auth_helper.py` - Use `python cli.py auth` instead
- `scripts/utilities/get_auth_url.py` - Automatic browser launch now

## Summary

✨ **No more manual authentication scripts!**  
✨ **Automatic browser launch**  
✨ **Smart token validation**  
✨ **Auto-save to .env.dev**  
✨ **Seamless re-authentication**  
✨ **Just run any command and start trading!**  

---

**Ready to trade?**

```bash
# 1. Set up credentials in .env.dev
# 2. Run any command
python cli.py start

# That's it! 🚀
```
