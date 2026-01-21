# Website Monitoring & Analytics Setup Guide

This guide explains how to set up comprehensive monitoring for foobos, including visitor analytics, uptime monitoring, performance tracking, and error logging.

## Overview

| Category | Solution | Status |
|----------|----------|--------|
| **Visitor Analytics** | Google Analytics 4 | Integrated (needs GA4 ID) |
| **Performance** | Lighthouse CI | Integrated (GitHub Actions) |
| **Uptime Monitoring** | UptimeRobot | External setup required |
| **Error Tracking** | GA4 Exception Events | Integrated |

---

## 1. Google Analytics 4 (Visitor Analytics)

### What You Get
- Real-time visitor counts
- Page views and unique visitors
- Geographic data
- Device/browser breakdown
- Traffic sources (referrals, search, direct)
- User behavior flow
- Custom event tracking

### Setup Instructions

1. **Create a Google Analytics 4 Property**
   - Go to [Google Analytics](https://analytics.google.com/)
   - Click "Admin" (gear icon)
   - Click "Create Property"
   - Enter property name: "foobos"
   - Select your timezone and currency
   - Click "Next" and complete the setup

2. **Get Your Measurement ID**
   - In Admin, go to "Data Streams"
   - Click "Add stream" → "Web"
   - Enter URL: `https://foobos.scottfriedman.ooo`
   - Enter stream name: "foobos Website"
   - Click "Create stream"
   - Copy the **Measurement ID** (format: `G-XXXXXXXXXX`)

3. **Add the Measurement ID to Your Environment**

   **Option A: GitHub Secrets (Recommended)**
   - Go to your GitHub repo → Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `GA4_MEASUREMENT_ID`
   - Value: Your `G-XXXXXXXXXX` measurement ID

   Update `.github/workflows/update-concerts.yml` to include the env var:
   ```yaml
   - name: Generate HTML
     env:
       GA4_MEASUREMENT_ID: ${{ secrets.GA4_MEASUREMENT_ID }}
     run: python main.py generate
   ```

   **Option B: Local .env file (for development)**
   Create or edit `.env` in the project root:
   ```
   GA4_MEASUREMENT_ID=G-XXXXXXXXXX
   ```

4. **Regenerate the HTML**
   ```bash
   python main.py generate
   ```

### Viewing Analytics
- Go to [Google Analytics](https://analytics.google.com/)
- Select your foobos property
- Key reports:
  - **Realtime**: See active users right now
  - **Acquisition**: Where visitors come from
  - **Engagement**: Page views, session duration
  - **Demographics**: User locations, devices

---

## 2. Performance Monitoring (Lighthouse CI)

### What You Get
- Automated performance audits after each deployment
- Historical performance tracking (stored in `data/performance/`)
- Core Web Vitals tracking
- Accessibility scores
- SEO scores
- Best practices compliance

### How It Works
The `lighthouse-ci.yml` workflow runs:
- Automatically after each concert listing update
- Weekly on Sundays for trend tracking
- Manually via workflow_dispatch

### Viewing Results
1. **GitHub Actions Summary**: Each run shows a performance table
2. **Artifacts**: Download detailed HTML reports from Actions → Artifacts
3. **Historical Data**: Check `data/performance/lighthouse-history.json`

### Performance Targets
| Metric | Target | Warning |
|--------|--------|---------|
| Performance | > 90% | < 50% |
| Accessibility | > 90% | < 90% (error) |
| Best Practices | > 90% | - |
| SEO | > 90% | - |

---

## 3. Uptime Monitoring (UptimeRobot)

### What You Get
- 24/7 uptime monitoring
- 5-minute check intervals (free tier)
- Email/SMS/Slack alerts when site goes down
- Uptime history and reports
- Public status page (optional)

### Setup Instructions

1. **Create UptimeRobot Account**
   - Go to [UptimeRobot](https://uptimerobot.com/)
   - Sign up for a free account

2. **Add Your Monitor**
   - Click "Add New Monitor"
   - Monitor Type: **HTTP(s)**
   - Friendly Name: `foobos`
   - URL: `https://foobos.scottfriedman.ooo`
   - Monitoring Interval: 5 minutes (free) or 1 minute (paid)
   - Click "Create Monitor"

3. **Configure Alerts**
   - Go to "My Settings" → "Alert Contacts"
   - Add your email, phone, or Slack webhook
   - Go back to your monitor and enable the alert contact

4. **Optional: Create Status Page**
   - Click "Status Pages" in the sidebar
   - Create a public status page for your site
   - Share the URL with users who want to check status

### Alternative Uptime Services
- [Better Uptime](https://betteruptime.com/) - Beautiful status pages
- [StatusCake](https://www.statuscake.com/) - More monitoring types
- [Pingdom](https://www.pingdom.com/) - Advanced features (paid)

---

## 4. Error Tracking

### What You Get
- JavaScript error capture in Google Analytics
- Error details: message, URL, line number
- Automatic tracking (no code changes needed)

### How It Works
The analytics script includes an `onerror` handler that sends JavaScript errors to GA4 as exception events.

### Viewing Errors
1. Go to Google Analytics
2. Navigate to: Reports → Engagement → Events
3. Look for events with name "exception"
4. Or create a custom exploration to analyze error patterns

### Upgrading to Dedicated Error Tracking
For more detailed error tracking, consider adding [Sentry](https://sentry.io/):

1. Create a Sentry account (free tier: 5K errors/month)
2. Create a new project for "Browser JavaScript"
3. Add the Sentry script to `html_header()` in `html_generator.py`

---

## 5. Quick Setup Checklist

- [ ] Create Google Analytics 4 property
- [ ] Get GA4 Measurement ID
- [ ] Add `GA4_MEASUREMENT_ID` to GitHub Secrets
- [ ] Update `update-concerts.yml` to pass the env var
- [ ] Regenerate HTML to include tracking
- [ ] Create UptimeRobot account and monitor
- [ ] Configure uptime alerts
- [ ] Verify Lighthouse CI workflow is running

---

## Data Locations

| Data Type | Location |
|-----------|----------|
| Visitor Analytics | Google Analytics dashboard |
| Performance History | `data/performance/lighthouse-history.json` |
| Lighthouse Reports | GitHub Actions Artifacts |
| Uptime History | UptimeRobot dashboard |
| Error Logs | Google Analytics Events |

---

## Privacy Considerations

Google Analytics 4 does track user data. If you're concerned about privacy:

1. **Enable IP Anonymization** (enabled by default in GA4)
2. **Consider alternatives**:
   - [Plausible](https://plausible.io/) - Privacy-focused, GDPR compliant
   - [GoatCounter](https://www.goatcounter.com/) - Simple, no cookies
   - [Umami](https://umami.is/) - Self-hosted, privacy-focused

To switch to a privacy-focused alternative, update `config.py` to use a different tracking script in `html_generator.py`.
