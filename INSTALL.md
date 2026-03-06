# How to Install BuzzBridge
# Rev: 1.1

This guide will walk you through setting up BuzzBridge step by step. No coding required!

## What You Need Before Starting

1. **An ecobee thermostat** that is already set up and working
2. **A Beestat account** (free) — we'll create this below
3. **Home Assistant** running on your computer or server

## Step 1: Create Your Beestat Account

1. Open your web browser and go to **https://app.beestat.io**
2. Click **"Sign in with ecobee"**
3. Log in with your ecobee email and password
4. Click **"Allow"** to let Beestat read your thermostat data
   - Beestat can only **read** data — it cannot change anything on your thermostat
   - Beestat never sees your ecobee password (it uses a secure connection called OAuth)
5. You should now see your thermostat data in Beestat — that means it's working!

## Step 2: Get Your Beestat API Key

The API key is like a special password that lets BuzzBridge talk to Beestat.

1. While logged into **https://app.beestat.io**, click the **menu icon** (three lines) in the top-left corner
2. Click **"API Key"**
3. You'll see a long string of letters and numbers (40 characters). This is your API key.
4. **Copy it** — you'll need it in a minute
   - Keep this key private! Anyone with it can read your thermostat data.

## Step 3: Install BuzzBridge in Home Assistant

### Option A: Using HACS (Easier)

If you have HACS (Home Assistant Community Store) installed:

1. Open Home Assistant in your browser
2. Click **HACS** in the sidebar
3. Click the **three dots** in the top-right corner
4. Click **"Custom repositories"**
5. In the "Repository" box, paste: `https://github.com/ChrisCaho/BuzzBridge`
6. In the "Category" dropdown, select **"Integration"**
7. Click **"Add"**
8. Now search for **"BuzzBridge"** in HACS and click **"Download"**
9. **Restart Home Assistant** (Settings → System → Restart)

### Option B: Manual Install

1. Download the BuzzBridge files from GitHub:
   **https://github.com/ChrisCaho/BuzzBridge**
2. Find the `custom_components/buzzbridge` folder in the download
3. Copy the entire `buzzbridge` folder into your Home Assistant's `custom_components` directory
   - The path should look like: `config/custom_components/buzzbridge/`
   - If you don't have a `custom_components` folder, create one
4. **Restart Home Assistant** (Settings → System → Restart)

## Step 4: Add BuzzBridge to Home Assistant

1. In Home Assistant, go to **Settings** (gear icon in the sidebar)
2. Click **"Devices & Services"**
3. Click the **"+ Add Integration"** button (bottom-right corner)
4. Search for **"BuzzBridge"**
5. Click on it
6. **Paste your API key** from Step 2
7. Optionally set a **device name prefix** (default: "BuzzBridge"). This prefix is added to all device and entity names so you can tell them apart from other integrations (e.g., "BuzzBridge Living Room"). Leave it blank if you don't want a prefix.
8. Click **"Submit"**

If everything works, you'll see a success message! BuzzBridge will automatically find all your thermostats and create sensors for them.

## Step 5: Find Your New Sensors

1. Go to **Settings → Devices & Services**
2. Click on **"BuzzBridge"**
3. You'll see your thermostats listed as devices
4. Click on any thermostat to see all the sensors created for it

You should see things like:
- Temperature and humidity
- What equipment is running (cooling, heating, fan)
- Hold status
- Air quality (if you have an ecobee Premium)
- Daily runtimes
- Remote sensor temperature, occupancy, and participating status
- And more!

## Step 6: Adjust Settings (Optional)

You can change how often BuzzBridge checks for new data:

1. Go to **Settings → Devices & Services**
2. Find **BuzzBridge** and click **"Configure"**
3. You'll see two settings:
   - **Fast poll interval** (default: 5 minutes) — how often to check temperature, humidity, and equipment status
   - **Slow poll interval** (default: 30 minutes) — how often to check daily runtime totals
4. Change them if you want, then click **"Submit"**

**Tip:** Don't set the fast poll lower than 3 minutes — Beestat's server only updates every 3 minutes anyway.

## Boost Polling (Cool Feature!)

Each thermostat has a **"Boost Polling"** button. When you press it:
- BuzzBridge temporarily checks for updates every **60 seconds** instead of every 5 minutes
- This lasts for **1 hour**, then goes back to normal
- Great for when you want to watch changes happen in real-time!

Find the button: Go to your thermostat device → look for the "Boost Polling" button entity.

## Troubleshooting

### "Invalid API key" error
- Make sure you copied the entire key (it should be exactly 40 characters)
- Go back to app.beestat.io and copy it again carefully
- Make sure there are no extra spaces before or after the key

### No sensors showing up
- Restart Home Assistant after installing
- Check that your Beestat account shows thermostat data at app.beestat.io
- Look at the Home Assistant logs for any error messages (Settings → System → Logs)

### Air quality sensors not showing
- Air quality sensors only work with the **ecobee Smart Thermostat Premium** model
- Other ecobee models don't have air quality sensors built in

### Data seems old or stale
- Beestat caches data for about 3 minutes on their server
- Your data will always be 3-5 minutes behind real-time — this is normal

## Need Help?

- Report issues: **https://github.com/ChrisCaho/BuzzBridge/issues**
- Check the full README for more details: **https://github.com/ChrisCaho/BuzzBridge**
