# PWA Installation Troubleshooting Guide

## Issue: PWA Install Error in Chrome

### Common Causes & Solutions

#### 1. **Clear Browser Cache** (Most Common Fix)

**On Android Chrome:**
```
1. Open Chrome
2. Tap ⋮ (three dots) → Settings
3. Privacy and security → Clear browsing data
4. Select "Cached images and files"
5. Tap "Clear data"
6. Close ALL Chrome tabs
7. Reopen https://www.zenalys.com/login
```

**Alternative: Hard Reset**
```
1. Open DevTools (F12 on desktop)
2. Right-click refresh button
3. Select "Empty Cache and Hard Reload"
```

#### 2. **Check if Manifest is Accessible**

Open in browser:
```
https://www.zenalys.com/manifest.json
```

**Expected:** Valid JSON response
**If 404:** Manifest not deployed correctly

#### 3. **Check if Icons Exist**

Test these URLs:
```
https://www.zenalys.com/icons/icon-192x192.png
https://www.zenalys.com/icons/icon-512x512.png
```

**Expected:** Icon images load
**If 404:** Icons missing from public folder

#### 4. **Check Service Worker Registration**

Open Chrome DevTools → Application tab:
```
1. Left sidebar: Service Workers
2. Check if service worker is registered
3. If red dot: Click "Unregister"
4. Refresh page
5. Service worker should re-register
```

#### 5. **Check PWA Installability**

Chrome DevTools → Application tab:
```
1. Left sidebar: Manifest
2. Check for errors (red X marks)
3. Common errors:
   - Missing start_url
   - Missing icons
   - Display mode not valid
```

#### 6. **HTTPS Requirement**

PWA requires HTTPS:
```
✅ https://www.zenalys.com (works)
❌ http://www.zenalys.com (won't work)
✅ http://localhost:3000 (works for dev)
```

### Quick Fix Steps

**For Users:**
```
1. Clear Chrome cache
2. Close ALL Chrome tabs
3. Reopen https://www.zenalys.com/login
4. Wait 5-10 seconds
5. PWA install banner should appear
6. If not: Tap ⋮ → Install app
```

**For Developers:**
```bash
# On VPS
cd /home/signalcraft

# Check if manifest exists
ls -la frontend/public/manifest.json
ls -la frontend/public/icons/

# Rebuild frontend
cd frontend
npm run build

# Restart containers
cd ..
docker compose down
docker compose up -d --build

# Clear service worker cache
# Open Chrome DevTools → Application → Clear storage → Clear site data
```

### Manifest Validation

Use Google's PWA validator:
```
https://manifest-validator.appspot.com/
```

Paste your manifest.json URL:
```
https://www.zenalys.com/manifest.json
```

### Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| "Manifest not found" | 404 on manifest.json | Check file exists in public folder |
| "No matching icon" | Icons missing | Check /icons/ folder has all sizes |
| "Invalid start_url" | start_url not in scope | Ensure start_url is within scope |
| "Service worker not registered" | SW not loaded | Check next-pwa config |
| "Install prompt not showing" | Already dismissed | Wait 7 days or clear site data |

### Android-Specific Issues

**Chrome on Android:**
```
1. Make sure Chrome is updated
2. Go to https://www.zenalys.com/login
3. Wait for page to fully load
4. Tap ⋮ (menu) → "Install app" or "Add to Home screen"
5. If option is greyed out:
   - Clear app cache (Settings → Apps → Chrome → Storage → Clear cache)
   - Try in Incognito mode
   - Update Chrome to latest version
```

### Testing Checklist

- [ ] Manifest accessible at `/manifest.json`
- [ ] All icons exist (72x72 to 512x512)
- [ ] Service worker registered
- [ ] Site served over HTTPS
- [ ] No console errors in DevTools
- [ ] PWA install banner appears
- [ ] "Add to Home Screen" option available

### If Still Not Working

**Nuclear Option:**
```
1. Uninstall any existing SignalCraft app
2. Clear ALL browsing data (not just cache)
3. Restart phone
4. Open https://www.zenalys.com/login in fresh Chrome
5. Wait 10 seconds
6. PWA install banner should appear
```

### Contact Info

If issue persists, provide:
1. Chrome version
2. Android version
3. Screenshot of error
4. Console errors from DevTools
5. Manifest validation results
