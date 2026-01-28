# 🚀 Quick Start - Integrated Authentication

## TL;DR - Get Started in 30 Seconds

```bash
# 1. Add your Kite API credentials to .env.dev
KITE_API_KEY=your_api_key
KITE_API_SECRET=your_api_secret

# 2. Run any command - authentication happens automatically!
python main.py
# OR
python cli.py start
# OR
python cli.py auth
```

That's it! The system will:
- ✅ Open your browser automatically
- ✅ Guide you through login
- ✅ Save your access token automatically
- ✅ Start trading immediately

---

## New Authentication System

### ✨ What's New?

**No more separate scripts!** Authentication is now seamlessly integrated into the application.

### Before (OLD) ❌
```bash
# Multiple steps, multiple scripts
python scripts/utilities/get_auth_url.py
# Copy URL, open browser manually...
python scripts/utilities/auth_helper.py auth
# Copy token, paste...
# Edit .env.dev manually...
python main.py
```

### After (NEW) ✅
```bash
# ONE command!
python main.py
# Browser opens → Login → Paste token → Done! 🎉
```

---

## Commands

### 🔐 Authenticate

```bash
# Method 1: Direct auth command
python cli.py auth

# Method 2: Any command will auto-authenticate
python cli.py start
python cli.py status
python main.py
```

### ✅ Check Authentication Status

```bash
python cli.py auth --validate-only
```

Output:
```
✅ Token is valid
   User: Your Name
   Email: your@email.com
   User ID: AB1234
```

### 🔄 Re-authenticate (if token expired)

```bash
# Just run auth again
python cli.py auth
```

---

## Setup

### 1️⃣ Get API Credentials

1. Visit https://kite.zerodha.com/apps
2. Create app or use existing
3. Note your **API Key** and **API Secret**

### 2️⃣ Update .env.dev

```bash
# Create from template
cp .env.example .env.dev

# Add your credentials
KITE_API_KEY=your_api_key_here
KITE_API_SECRET=your_api_secret_here
```

### 3️⃣ Run!

```bash
python main.py
```

The system will:
1. 🌐 Open browser with login page
2. 👤 You login with Zerodha credentials
3. 📋 Browser redirects with request_token
4. 📝 You paste the token
5. ✅ System saves access token
6. 🚀 Trading system starts!

---

## How It Works

### Smart Authentication Flow

```
┌─────────────────┐
│  Run Command    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     Valid?
│ Check Token     │────────────► Continue ✅
└────────┬────────┘      YES
         │ NO
         ▼
┌─────────────────┐
│ Open Browser    │◄── Automatic!
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ User Logs In    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Paste Token     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Save to .env    │◄── Automatic!
└────────┬────────┘
         │
         ▼
      Continue ✅
```

---

## Features

### 🌐 Auto Browser Launch
Opens Kite login page automatically - no URL copying needed!

### ✅ Smart Token Validation
Checks existing token before prompting - only authenticates when needed.

### 💾 Auto-Save
Saves access token to .env.dev automatically - no manual file editing!

### 🔄 Seamless Re-auth
Token expired? System detects and re-authenticates automatically.

### 🎯 Clear Guidance
Helpful messages guide you through each step.

---

## Troubleshooting

### Browser Doesn't Open?
The URL is shown in terminal - copy and open manually:
```
⚠️ Could not open browser automatically.
Please manually open this URL:
https://kite.zerodha.com/connect/login?api_key=...
```

### "Request token expired"?
Request tokens expire in ~2 minutes. Just run auth again:
```bash
python cli.py auth
```

### "Invalid access token"?
Access tokens expire after 24 hours. System will auto re-authenticate:
```bash
python cli.py start
# If token expired, system will open browser for re-auth
```

### Missing API credentials?
Update your .env.dev file:
```bash
KITE_API_KEY=your_api_key
KITE_API_SECRET=your_api_secret
```

---

## Daily Workflow

### Morning (First Trade of the Day)

```bash
# Start the system
python cli.py start

# If token expired (after 24 hours):
# → Browser opens automatically
# → Login and paste token
# → System continues

# Token still valid:
# → System starts immediately ✅
```

### During the Day

```bash
# Check status
python cli.py status

# Monitor live
python cli.py monitor

# View signals
python cli.py signals --limit 20

# No re-authentication needed! ✨
```

### Evening

```bash
# Stop system
python cli.py stop

# Review performance
python cli.py performance --days 1
```

---

## Programmatic Usage

### In Your Code

```python
from src.auth import get_auth_manager

# Get auth manager
auth_manager = get_auth_manager()

# Ensure authenticated (interactive)
if await auth_manager.ensure_authenticated(interactive=True):
    # Opens browser if needed
    profile = auth_manager.get_profile()
    print(f"Logged in as: {profile['user_name']}")
```

### With KiteAPIClient

```python
from src.api.kite_client import KiteAPIClient

# Initialize with auto-auth
client = KiteAPIClient()
await client.initialize(auto_authenticate=True)

# System handles authentication automatically!
# If token missing/invalid, opens browser
```

---

## Security

### ✅ Best Practices

- Keep `.env.dev` in `.gitignore` (already configured)
- Never commit API secrets
- Use paper trading for testing: `PAPER_TRADING=true`
- Review app permissions on Kite portal

### 🔒 Token Management

- Access tokens expire after 24 hours (Kite policy)
- System validates on startup
- Auto re-authenticates when expired
- Tokens saved securely in .env.dev

---

## Comparison with Old System

| Feature | Old System ❌ | New System ✅ |
|---------|--------------|--------------|
| **Commands** | 3 separate scripts | 1 command |
| **Browser** | Manual URL copy | Auto-opens |
| **Token Save** | Manual edit | Automatic |
| **Steps** | 9 steps | 2 steps (login + paste) |
| **User Friendly** | Complex | Simple |
| **Support Burden** | High | Low |

---

## Complete Example

### First Time Setup

```bash
# Terminal Session:

$ python main.py

🚀 Starting AlphaStock Trading System
==========================================================

🔑 KITE CONNECT AUTHENTICATION REQUIRED
================================================================================
📋 Authentication Steps:
1. Your browser will open with the Kite login page
2. Login with your Zerodha credentials
3. After successful login, copy the 'request_token' from the URL
4. Paste it back here when prompted

--------------------------------------------------------------------------------
🌐 Opening browser for authentication...
[Browser opens: https://kite.zerodha.com/connect/login?api_key=...]

--------------------------------------------------------------------------------
After login, the URL will look like:
https://127.0.0.1:8080/?request_token=XXXXXX&action=login&status=success
                              ^^^^^^^^^^^^^^^^^^^^^^^^
                              Copy this part!
--------------------------------------------------------------------------------

🔑 Paste the request_token here: abcd1234efgh5678ijkl

🔄 Generating session...

================================================================================
✅ AUTHENTICATION SUCCESSFUL!
================================================================================
✓ User: John Doe
✓ User ID: AB1234
✓ Email: john@example.com
✓ Access token saved to .env.dev
================================================================================

✅ System initialized successfully
Starting trading system...
✅ Trading system started

# That's it! 🎉
```

---

## Need Help?

📚 **Full Documentation**: `docs/INTEGRATED_AUTH.md`  
📝 **Implementation Details**: `docs/AUTH_IMPLEMENTATION_SUMMARY.md`  
🐛 **Issues**: Check logs in `logs/` folder  
💬 **Questions**: Review the documentation files

---

## Summary

### What You Need to Know

1. **Setup**: Add API credentials to `.env.dev` (one-time)
2. **Run**: `python main.py` or `python cli.py auth`
3. **Login**: Browser opens → Login → Paste token
4. **Done**: System saves token and starts trading

### Key Benefits

✨ **Automatic** - Browser launches automatically  
✨ **Smart** - Validates before prompting  
✨ **Persistent** - Saves tokens automatically  
✨ **Seamless** - Re-authenticates when needed  
✨ **Simple** - Just one command!  

---

**Ready to trade? Just run:**

```bash
python main.py
```

**That's it! The system handles the rest.** 🚀
