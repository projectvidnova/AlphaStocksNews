# 🔑 Setting Up Your Kite API Credentials

## Quick Setup Guide

### Step 1: Get Your API Credentials

1. Go to [Kite Connect Developer Portal](https://kite.zerodha.com/apps)
2. Log in with your Zerodha credentials
3. Create a new app or use an existing one
4. Note down your:
   - **API Key** (Public, visible in app details)
   - **API Secret** (Private, show only once - save it!)

### Step 2: Update `.env.dev` File

The `.env.dev` file has been created with template values. Open it and update:

```bash
# Replace these three values with your actual credentials:
KITE_API_KEY=your_actual_api_key_from_kite_portal
KITE_API_SECRET=your_actual_api_secret_from_kite_portal
KITE_ACCESS_TOKEN=will_be_generated_in_step_3
```

### Step 3: Authenticate with Zerodha

Access tokens expire daily. Use the integrated authentication system:

#### Quick Authentication (Recommended)
```bash
python cli.py auth
```
This will:
1. Automatically open your browser with Zerodha login page
2. After you login, copy the `request_token` from the redirect URL
3. Paste the token when prompted
4. Automatically save the access token to `.env.dev`

#### Check Existing Token
```bash
# Validate current token without prompting
python cli.py auth --validate-only
```

#### Test Authentication
```bash
# Quick test utility
python test_auth.py
```

**📖 For detailed authentication guide, see [AUTHENTICATION.md](AUTHENTICATION.md)**

### Step 4: Verify Configuration

```bash
# Test your credentials
python3 scripts/utilities/validate_system.py

# Or run the complete workflow
python3 complete_workflow.py
```

## Important Notes

### 🔒 Security
- **NEVER commit `.env.dev` to git** - it's already in `.gitignore`
- Keep your API Secret safe - it's shown only once when you create the app
- Access tokens expire daily - you'll need to regenerate them

### 📝 Paper Trading vs Live Trading
The system is set to paper trading by default:
```bash
PAPER_TRADING=true  # ✅ Safe - no real money
```

**Before going live:**
1. Test thoroughly with paper trading for several weeks
2. Understand all strategies and risk management
3. Change to `PAPER_TRADING=false` only when ready
4. Start with small capital

### 🔄 Daily Access Token Regeneration

Since access tokens expire daily, regenerate each morning before market opens:

```bash
# Authenticate (auto-launches browser)
python cli.py auth

# Or use quick test utility
python test_auth.py
```

The system will automatically validate your existing token and only prompt for new authentication if needed.

**📖 For advanced authentication options, see [AUTHENTICATION.md](AUTHENTICATION.md)**

### 📊 After Setup

Once configured, you can:

```bash
# Start the trading system
python3 cli.py start

# Monitor in real-time
python3 cli.py monitor

# Check system status
python3 cli.py status

# View recent signals
python3 cli.py signals --limit 20

# Stop the system
python3 cli.py stop
```

## Troubleshooting

### "API key not found"
- Check that `.env.dev` exists in the project root
- Ensure `KITE_API_KEY` is set (no quotes needed)
- Restart the application after updating `.env.dev`

### "Authentication failed"
- Verify your API Key and Secret are correct
- Check if your access token is still valid (regenerate if needed)
- Ensure your Kite Connect app is active on the developer portal

### "Invalid access token"
- Access tokens expire after 24 hours
- Generate a new one using the helper script
- Update `KITE_ACCESS_TOKEN` in `.env.dev`

### "Insufficient permissions"
- Check your Kite Connect app permissions
- Ensure it has permissions for:
  - Market data
  - Portfolio
  - Orders (if live trading)

## Support Resources

- **Kite Connect Docs**: https://kite.trade/docs/connect/v3/
- **API Forum**: https://kite.trade/forum/
- **Zerodha Support**: https://support.zerodha.com/

## Environment Variables Reference

### Required
- `KITE_API_KEY` - Your Kite Connect API Key
- `KITE_API_SECRET` - Your Kite Connect API Secret  
- `KITE_ACCESS_TOKEN` - Daily access token

### Optional
- `KITE_REQUEST_TOKEN` - Temporary token from auth flow
- `KITE_USER_ID` - Your Zerodha Client ID
- `PAPER_TRADING` - Enable paper trading (default: true)
- `PAPER_CAPITAL` - Initial capital for paper trading (default: 100000)
- `LOG_LEVEL` - Logging detail level (default: INFO)
- `DEBUG_MODE` - Enable detailed debugging (default: false)

---

**Ready to trade?** Update your credentials in `.env.dev` and run the system! 🚀
