# 🔧 Discord Bot Deployment - Troubleshooting Guide

## 🚫 Error 429: Rate Limit

If you're getting **"429 Too Many Requests"** when deploying to Render.com:

### ⚠️ **CRITICAL: Regenerate Your Discord Token**

Your token is likely compromised or flagged. **This is the #1 fix:**

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Select your bot application
3. Click **"Bot"** in the left sidebar
4. Click **"Reset Token"** button
5. Copy the new token (you won't be able to see it again!)
6. Update your token:
   - **Local**: Update `DISCORD_TOKEN` in your `.env` file
   - **Render.com**: Go to your service → Environment → Update `DISCORD_TOKEN`

### 📝 Common Causes

#### 1. **Token Exposed in Git History**
If your token was ever committed to GitHub, Discord auto-revokes it.

**Check your git history:**
```bash
git log -p | grep -i "discord_token"
```

**If found:**
- Regenerate your token (see above)
- Add `.env` to `.gitignore`
- Never commit tokens again!

#### 2. **Rapid Restart Loop**
If your bot crashes repeatedly, Discord blocks the IP temporarily.

**Fix:**
- Wait 10-15 minutes before deploying again
- Check your Render logs for the root cause of crashes
- Ensure `MONGO_URI` and `DISCORD_TOKEN` are set correctly

#### 3. **Shared Hosting IP Flagged**
Render.com and other hosting providers use shared IPs that may be temporarily flagged.

**Fix:**
- Regenerate your token
- Wait a few minutes
- Redeploy

## 🔑 Invalid Token Error

If you see **"INVALID DISCORD TOKEN"** in logs:

1. Verify your token doesn't include `Bot ` prefix
2. Check for extra spaces or characters
3. Regenerate the token if needed (see above)

## 🐛 Bugs Fixed in This Update

### ✅ 8 AM Scheduling Bug Fixed
**Before:** Events scheduled for wrong day (skipped to day after tomorrow)  
**After:** Correctly schedules for today (if before 8 AM) or tomorrow (if after 8 AM)

### ✅ Enhanced Error Handling
- Added specific handling for Discord 429 rate limit errors
- Added helpful troubleshooting messages
- Prevents crash-restart loops with 60-second cooldown

## 📦 Deployment Checklist

Before deploying to Render.com:

- [ ] Set `DISCORD_TOKEN` environment variable
- [ ] Set `MONGO_URI` environment variable
- [ ] Ensure `.env` is in `.gitignore`
- [ ] Token is freshly regenerated (not reused)
- [ ] MongoDB connection string is correct
- [ ] Dependencies installed (`requirements.txt`)

## 🆘 Still Having Issues?

1. **Check Render Logs:**
   - Look for specific error messages
   - Verify environment variables are set

2. **Test Locally First:**
   ```bash
   python main.py
   ```
   Make sure it connects successfully locally before deploying

3. **Verify Discord Bot Settings:**
   - Ensure bot has proper intents enabled (Server Members, Message Content)
   - Bot must be invited to at least one server

## 📞 Discord API Rate Limits

Discord enforces rate limits to prevent abuse:
- **Login attempts:** Limited per IP
- **Invalid tokens:** Trigger automatic blocks
- **Recommended:** Wait at least 60 seconds between retries

The bot now automatically waits 60 seconds when rate limited to prevent making it worse.
