# Mobile View Test Guide

## How to Test Mobile Responsiveness

### On Desktop (Chrome DevTools)
1. Open `https://www.zenalys.com` in Chrome
2. Press `F12` to open DevTools
3. Press `Ctrl+Shift+M` (or click the device toggle icon)
4. Select a mobile device (e.g., "iPhone 12 Pro" or "Pixel 5")
5. Login to your account
6. You should see:

**Mobile View Checklist:**
- [ ] ☐ Desktop sidebar is HIDDEN
- [ ] ☐ Hamburger menu (☰) is VISIBLE in top-left
- [ ] ☐ Mobile header with gradient background is visible
- [ ] ☐ Bottom navigation bar with 6 items (Home, Build, Backtest, Live, Settings, Logout)
- [ ] ☐ Dashboard content is full-width (no sidebar taking space)
- [ ] ☐ Index cards show 2 columns (not 4)
- [ ] ☐ Stats cards show 2 columns (not 4)

**Test Hamburger Menu:**
- [ ] ☐ Tap hamburger (☰) - sidebar slides in from left
- [ ] ☐ Sidebar shows all navigation items
- [ ] ☐ Tap overlay or press ESC - sidebar closes
- [ ] ☐ Tap a navigation item - sidebar closes and page navigates

**Test Logout:**
- [ ] ☐ Tap "Logout" button in bottom nav
- [ ] ☐ Confirmation modal appears
- [ ] ☐ Tap "Cancel" - modal closes
- [ ] ☐ Tap "Logout" - logs out and redirects to login

**Test PWA Install:**
- [ ] ☐ Look for "📲 Install SignalCraft" prompt above bottom nav
- [ ] ☐ Tap "Install" - app installs to home screen
- [ ] ☐ Launch from home screen - opens in full-screen mode

### On Actual Mobile Device
1. Open `https://www.zenalys.com` on your Android phone
2. Login to your account
3. Verify the same checklist as above

## Expected Mobile Layout

```
┌─────────────────────────────────────┐
│ ☰ Welcome back, User 👋            │ ← Mobile Header
├─────────────────────────────────────┤
│ [NIFTY] [BANKNIFTY]                │ ← Index cards (2 columns)
│ [FINNIFTY] [MORE]                  │
├─────────────────────────────────────┤
│ Today's P&L    │ Active Strategies │ ← Stats (2 columns)
│ Orders Today   │ Win Rate          │
├─────────────────────────────────────┤
│ Active Strategies Card             │
│ ┌────────────────────────────────┐ │
│ │ Strategy 1                     │ │
│ │ Strategy 2                     │ │
│ └────────────────────────────────┘ │
├─────────────────────────────────────┤
│ Quick Actions │ Recent Backtests   │
│               │                    │
└─────────────────────────────────────┘
┌─────────────────────────────────────┐
│ 🏠  ⚡  📊  🔴  ⚙️  🚪             │ ← Bottom Nav
│Home Build Back Live Set  Logout    │
└─────────────────────────────────────┘
```

## Troubleshooting

### Desktop sidebar still showing on mobile?
- Clear browser cache
- Hard refresh: `Ctrl+Shift+R` (or `Cmd+Shift+R` on Mac)
- Check browser console for errors

### Hamburger menu not showing?
- Make sure you're logged in (not on landing page)
- Check if screen width is < 768px
- Verify `ConditionalSidebar.tsx` is updated

### PWA install prompt not showing?
- Must be on HTTPS (✅ zenalys.com has HTTPS)
- Must not have dismissed in last 7 days
- Check browser console for `[PWA]` logs

## Deploy to VPS

SSH into your VPS and run:
```bash
cd /home/signalcraft
git pull origin main && docker compose up -d --build
```

Wait for build to complete (~2-3 minutes), then test.
