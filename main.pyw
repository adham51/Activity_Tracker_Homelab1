# ── Imports ──────────────────────────────────────────────────────────────────
import time          # Allows us to pause the script using time.sleep()
import logging       # Upgraded version of print() that adds timestamps to messages
import signal        # Lets us detect OS signals (like when you press Ctrl+C to quit)
import sys           # Lets us force the Python script to shut down cleanly
import os            # Lets us read Environment Variables (system-wide hidden settings)

# AWS
import requests
import boto3
from botocore.exceptions import ClientError

from datetime import datetime, timezone
import zoneinfo
CAIRO_TZ = zoneinfo.ZoneInfo("Africa/Cairo")
from typing import Optional      # Helps with code auto-complete, says a value might be 'None'
from urllib.parse import urlparse  # A tool to chop up a URL and extract just the domain name (e.g., github.com)
import re

import psycopg2      # The bridge/driver that connects Python to your PostgreSQL database
import pygetwindow as gw  # A tool that asks the Windows/Linux OS: "What window is on top right now?"

from dotenv import load_dotenv
load_dotenv()  # This physically finds the .env file and loads the variables!

# ── Settings ─────────────────────────────────────────────────────────────────

# This dictionary stores all the login info for your database.
# os.getenv("DB_HOST", "localhost") means: "Look for an environment variable named DB_HOST. 
# If you don't find it, just use 'localhost' as a backup."
DB_CONFIG = {
    "host":     os.getenv("DB_HOST"),            # Server address
    "port":     int(os.getenv("DB_PORT", "5432")),                # Port number (converted to integer)
    "dbname":   os.getenv("DB_NAME"), # Database name
    "user":     os.getenv("DB_USER"),                 # Username
    "password": os.getenv("DB_PASSWORD"),                 # Password
}

# The number of seconds the script will wait before checking your screen again.
POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "2"))

# Controls how chatty the script is. "INFO" prints standard messages.
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


# A translation dictionary. If the window title contains any of the words in the list,
# the script will rename it to the clean key on the left.
KNOWN_APPS = {
    # ── Browsers ──
    "Google Chrome": ["Google Chrome", "Chrome"],
    "Firefox":       ["Mozilla Firefox", "Firefox"],
    "Edge":          ["Microsoft Edge", "Edge"],

    # ── IDEs & Text Editors ──
    "VS Code":       ["Visual Studio Code", "Code - OSS"],
    "Visual Studio": ["Visual Studio", "devenv"],
    "PyCharm":       ["PyCharm"],
    "CLion":         ["CLion"],
    "NetBeans":      ["NetBeans"],
    "Arduino IDE":   ["Arduino"],
    "CodeBlocks":    ["Code::Blocks", "CodeBlocks"],
    "Notepad++":     ["Notepad++"],
    "Cursor":        ["Cursor"],

    # ── DevOps, Networking & DB Tools ──
    "DBeaver":       ["DBeaver"],
    "Postman":       ["Postman"],
    "Docker":        ["Docker Desktop", "Docker"],
    "VMware":        ["VMware Workstation", "VMware"],
    "VirtualBox":    ["VirtualBox"],
    "PuTTY":         ["PuTTY"],
    "Wireshark":     ["Wireshark"],
    "Packet Tracer": ["Cisco Packet Tracer", "Packet Tracer"],
    "XAMPP":         ["XAMPP Control Panel", "XAMPP"],
    "Vivado":        ["Vivado"],
    "GitHub":        ["GitHub Desktop"],

    # ── Terminals ──
    "Terminal":      ["Terminal", "bash", "zsh", "Command Prompt", "PowerShell", "MSYS2"],

    # ── Communication ──
    "Discord":       ["Discord"],
    "Teams":         ["Microsoft Teams", "Teams"],
    "Zoom":          ["Zoom"],
    "Telegram":      ["Telegram"],
    "Slack":         ["Slack"],

    # ── Productivity ──
    "Obsidian":      ["Obsidian"],
    "Word":          ["Microsoft Word", "Word"],
    "Excel":         ["Microsoft Excel", "Excel"],
    "PowerPoint":    ["Microsoft PowerPoint", "PowerPoint"],
    "Outlook":       ["Outlook"],

    # ── Media & Gaming ──
    "Spotify":       ["Spotify"],
    "Steam":         ["Steam"],
    "League of Legends": ["League of Legends", "Riot Client"],
    "VLC":           ["VLC media player", "VLC"],
    "Bandicam":      ["Bandicam"],

    # ── Remote Access ──
    "AnyDesk":       ["AnyDesk"],
    "TeamViewer":    ["TeamViewer"],
    "UltraViewer":   ["UltraViewer"],
    "Remote Desktop": ["Remote Desktop Connection"],
}
# Maps title keywords → clean site name
# Checked BEFORE generic separator splitting in classify_app()
# Keys = clean display name, Values = substrings to look for in the title
KNOWN_SITES = {
    # ════════════════════════════════════════════════════════════════════════
    # ── TIER 1: INTERCEPTORS (checked first — order matters!) ────────────
    # These must be at the top because their keywords would also match
    # generic entries below (e.g. "aws" would match YouTube AND AWS site)
    # ════════════════════════════════════════════════════════════════════════

    # Catches educational YouTube before the generic YouTube entry below
    "YouTube (Learning)": [
        # Arabic
        "شرح", "كورس", "محاضرة",  "cert", "certification", "exam", "associate",
        # General learning signals
        "tutorial", "course", "crash course", "roadmap",
        "explained", "how to", "beginner", "advanced", "full course",
    ],

    # Catches Udemy course pages before generic separator split
    "Udemy":           ["| Udemy", "On Your Schedule | Udemy", "udemy.com"],

    # ════════════════════════════════════════════════════════════════════════
    # ── TIER 2: DEEP WORK & CODING ────────────────────────────────────────
    # ════════════════════════════════════════════════════════════════════════
    "GitHub":          ["· github", "· Issue #", "· Pull Request #",
                        "· GitHub", " - GitHub", "github.com"],
    "Stack Overflow":  ["- Stack Overflow", "| Stack Overflow"],
    "AWS":             ["- AWS", "| AWS", "AWS Certified",
                        "Amazon Web Services", "console.aws.amazon"],
    "Google Cloud":    ["- Google Cloud", "| Google Cloud",
                        "console.cloud.google"],
    "Codeforces":      ["- Codeforces", "| Codeforces"],
    "Overleaf":        ["- Overleaf", "Online LaTeX Editor Overleaf"],
    "Mermaid":         ["Mermaid Live Editor"],
    "Grafana Docs":    ["Grafana documentation"],
    "Grafana":         ["- Grafana", "| Grafana"],

    # ════════════════════════════════════════════════════════════════════════
    # ── TIER 3: LEARNING & AI RESEARCH ────────────────────────────────────
    # ════════════════════════════════════════════════════════════════════════
    "Claude":          ["- Claude"],
    "ChatGPT":         ["- ChatGPT", "ChatGPT"],
    "Google Gemini":   ["- Google Gemini", "Google Gemini"],
    "NotebookLM":      ["- NotebookLM", "NotebookLM"],
    "Medium":          ["| Medium", "- Medium"],
    "Hashnode":        ["- Hashnode", "| Hashnode"],
    "Dev.to":          ["- DEV Community", "DEV Community"],
    "freeCodeCamp":    ["- freeCodeCamp", "freeCodeCamp"],

    # ════════════════════════════════════════════════════════════════════════
    # ── TIER 4: CAREER & JOB HUNTING ──────────────────────────────────────
    # ════════════════════════════════════════════════════════════════════════
    "LinkedIn":        ["| LinkedIn", "Feed | LinkedIn",
                        "Notifications | LinkedIn", "LinkedIn"],
    "Wuzzuf":          ["- Wuzzuf", "| Wuzzuf"],
    "Vodafone Jobs":   ["jobs.vodafone.com"],
    "Siemens Jobs":    ["jobs.siemens.com"],
    "PwC Jobs":        ["pwc.wd3.myworkdayjobs", "- PwC"],
    "Deloitte Jobs":   ["middleeastjobs.deloitte"],

    # ════════════════════════════════════════════════════════════════════════
    # ── TIER 5: COMMUNICATION & ADMIN ─────────────────────────────────────
    # ════════════════════════════════════════════════════════════════════════
    "Gmail":           ["- Gmail", "Gmail", "mail.google.com"],
    "Outlook":         ["outlook.cloud.microsoft", "outlook.office.com",
                        "outlook.live.com"],
    "Google Meet":     ["- Google Meet", "Google Meet"],
    "Google Drive":    ["- Google Drive", "Google Drive"],
    "Google Docs":     ["- Google Docs"],
    "Google Sheets":   ["- Google Sheets"],
    "WhatsApp Web":    ["WhatsApp", "web.whatsapp.com"],
    "Notion":          ["- Notion", "| Notion"],
    "forms.office":    ["Microsoft Forms", "forms.office.com"],

    # ════════════════════════════════════════════════════════════════════════
    # ── TIER 6: ENTERTAINMENT & DISTRACTIONS (checked last!) ──────────────
    # ════════════════════════════════════════════════════════════════════════
    "YouTube Music":   ["YouTube Music"],           # must be before YouTube
    "YouTube":         ["- YouTube", "youtube.com"],
    "Facebook":        ["| Facebook", "Facebook"],
    "Instagram":       ["• Instagram", "Instagram"],
    "TikTok":          ["| TikTok", "TikTok"],

    # ════════════════════════════════════════════════════════════════════════
    # ── TIER 7: UTILITIES (neutral — excluded from category charts) ────────
    # ════════════════════════════════════════════════════════════════════════
    "Google Search":   ["- Google Search", "Google Search"],
    "Speedtest":       ["Speedtest", "fast.com"],
    "Chrome Web Store":["Chrome Web Store"],
}

# ── Logging setup ─────────────────────────────────────────────────────────────

# This configures our 'log' tool. Instead of standard text, it formats it as: "Time [Level] Message"
# It routes the output to two places: the terminal screen, AND a text file named 'tracker.log'.
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),           # spits logs out to the terminal
        logging.FileHandler("tracker.log", encoding="utf-8")  # saves logs to a file with UTF-8 encoding to support all characters
    ],
)
# Creates the actual log object we will use later to print things.
log = logging.getLogger(__name__)


# AWS SG/IP CHECK FUNCTION
def ensure_aws_access():
    """Updates EXISTING Security Group rules with the new dynamic IP."""
    sg_id = os.getenv("AWS_SG_ID")
    if not sg_id:
        return

    try:
        # 1. Get current public IP
        my_ip = requests.get('https://api.ipify.org').text + '/32'
        
        # 2. Connect to AWS EC2
        ec2 = boto3.client('ec2', region_name=os.getenv("AWS_REGION", "eu-central-1"))
        
        # 3. Define the exact rules to update using your AWS Rule IDs
        rules_to_update = [
            {
                'SecurityGroupRuleId': 'sgr-0055c4fb6016063e5', # SSH
                'SecurityGroupRule': {
                    'IpProtocol': 'tcp',
                    'FromPort': 22,
                    'ToPort': 22,
                    'CidrIpv4': my_ip,
                    'Description': 'Auto-updated SSH'
                }
            },
            {
                'SecurityGroupRuleId': 'sgr-0e8860add822ebf80', # PostgreSQL
                'SecurityGroupRule': {
                    'IpProtocol': 'tcp',
                    'FromPort': 5432,
                    'ToPort': 5432,
                    'CidrIpv4': my_ip,
                    'Description': 'Auto-updated POSTGRESQL DB'
                }
            },
            {
                'SecurityGroupRuleId': 'sgr-08b4e67e6487ab3f0', # Custom TCP
                'SecurityGroupRule': {
                    'IpProtocol': 'tcp',
                    # NOTE: Update these ports to match whatever this rule is actually for!
                    # For example, if this is Grafana, change 3000 to 3000. 
                    # If it is Portainer, change to 9000.
                    'FromPort': 3000, 
                    'ToPort': 3000,   
                    'CidrIpv4': my_ip,
                    'Description': 'Auto-updated GRAFANA'
                }
            }
        ]
        
        # 4. Push the update to AWS
        ec2.modify_security_group_rules(
            GroupId=sg_id,
            SecurityGroupRules=rules_to_update
        )
        log.info(f"AWS SG successfully modified. Rules updated to IP: {my_ip}")
        
    except ClientError as e:
        log.error(f"Failed to update AWS Security Group: {e}")
    except Exception as e:
        log.error(f"Could not check or update IP: {e}")
        
# ── Database schema ───────────────────────────────────────────────────────────

# This is raw SQL language saved as a giant multi-line Python string.
SCHEMA_SQL = """
-- Creates the 'sessions' table if it doesn't already exist.
CREATE TABLE IF NOT EXISTS sessions (
    id            SERIAL PRIMARY KEY,   -- Automatic ID number (1, 2, 3...)
    app_name      TEXT        NOT NULL, -- Clean app name (Required)
    window_title  TEXT,                 -- Messy full window title (Optional)
    started_at    TIMESTAMPTZ NOT NULL, -- Exact time you switched to it (Timezone aware)
    ended_at      TIMESTAMPTZ,          -- Exact time you left it (Empty until you leave)

    -- Database automatically calculates (ended - started) to get total seconds.
    duration_secs INTEGER GENERATED ALWAYS AS (
        EXTRACT(EPOCH FROM (ended_at - started_at))::INTEGER
    ) STORED
);

-- Creates indexes (like the index of a book) to make searching by app_name or start_date lightning fast.
CREATE INDEX IF NOT EXISTS idx_sessions_app     ON sessions (app_name);
CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions (started_at);

-- Creates the 'daily_stats' table to store pre-calculated totals for Grafana.
CREATE TABLE IF NOT EXISTS daily_stats (
    stat_date     DATE    NOT NULL,               -- Just the calendar day
    app_name      TEXT    NOT NULL,               -- Clean app name
    total_secs    INTEGER NOT NULL DEFAULT 0,     -- Total seconds spent today
    session_count INTEGER NOT NULL DEFAULT 0,     -- Number of times opened today
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(), -- Last time this row was touched
    PRIMARY KEY (stat_date, app_name)             -- Ensures only ONE row per app, per day
);
"""


# ── Database functions ────────────────────────────────────────────────────────

def init_db(conn):
    # 'with conn.cursor() as cur' hires a temporary database worker (cursor) 
    # to run our SQL command, then immediately fires the worker when done.
    with conn.cursor() as cur:
        cur.execute(SCHEMA_SQL)  # Tells the worker to build the tables
    log.info("Database tables are ready.")


def open_session(conn, app: str, title: Optional[str], started_at: datetime):
    # Hires a worker to INSERT a brand new row into the sessions table.
    with conn.cursor() as cur:
        cur.execute(
            # Using %s is a security feature. It safely replaces %s with your variables.
            "INSERT INTO sessions (app_name, window_title, started_at) VALUES (%s, %s, %s)",
            (app, title, started_at),
        )


def close_session(conn, app: str, title: Optional[str], started_at: datetime, ended_at: datetime):
    # Hires a worker for a two-part job: Closing the old session, and updating daily stats.
    
    # Task 1: Find the open session (where ended_at is empty) and fill in the end time.
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE sessions
            SET ended_at = %s
            WHERE id = (
                SELECT id FROM sessions
                WHERE  app_name   = %s
                  AND  started_at = %s
                  AND  ended_at IS NULL
                ORDER BY id DESC
                LIMIT 1
            )
            """,
            (ended_at, app, started_at),
        )

   # Task 2: Calculate all the time spent in this app today, and update the summary table.
    with conn.cursor() as cur: 
        cur.execute(
            """
            INSERT INTO daily_stats (stat_date, app_name, total_secs, session_count, updated_at)

            -- This SELECT grabs all completed sessions for this app today and sums them up
            SELECT
                DATE(started_at AT TIME ZONE 'Africa/Cairo'),
                app_name,
                SUM(duration_secs),
                COUNT(*),
                NOW()
            FROM sessions
            WHERE app_name        = %s
              AND DATE(started_at AT TIME ZONE 'Africa/Cairo') = %s
              AND ended_at IS NOT NULL
            GROUP BY DATE(started_at AT TIME ZONE 'Africa/Cairo'), app_name

            -- If this app already has a summary row for today, just update it instead of making a new one.
            ON CONFLICT (stat_date, app_name) DO UPDATE
                SET total_secs    = EXCLUDED.total_secs,
                    session_count = EXCLUDED.session_count,
                    updated_at    = NOW()
            """,
            (app, started_at.date()),
        )


# ── Window detection functions ────────────────────────────────────────────────
def classify_app(title: str) -> str:
    """
    Takes a raw window title and returns a clean app name.
    """

    # ── 1. Intercept Files and Terminals FIRST ───────────────────────────────
    # This MUST be at the very top of the function!
    
    if "cmd.exe" in title.lower() or "powershell" in title.lower():
        return "Terminal"

    # Looks for shapes like "C:\" or "(D:)"
    if re.search(r'[A-Za-z]:\\', title) or re.search(r'\([A-Za-z]:\)', title):
        return "File Explorer"
    
    # Loop through our KNOWN_APPS dictionary to see if this title belongs to a known app.
    for app_name, keywords in KNOWN_APPS.items():
        if any(kw.lower() in title.lower() for kw in keywords):

            # ── Special Chrome handling ───────────────────────────────────────
            if app_name in ("Google Chrome", "Chromium"):

                # Strip the browser name from the end
                clean = title
                for browser_suffix in [" - Google Chrome", " - Chromium"]:
                    clean = clean.replace(browser_suffix, "").strip()

                # ── KNOWN_SITES lookup ────────────────────────────────────────
                # Handles sites with unusual separators (GitHub uses ·, LinkedIn uses |)
                # Checked BEFORE generic splitting so it takes priority
                clean_lower = clean.lower()
                for site_name, keywords in KNOWN_SITES.items():
                    if any(kw.lower() in clean_lower for kw in keywords):
                        return f"Chrome: {site_name}"
                # ─────────────────────────────────────────────────────────────

                # Generic separator split — covers most remaining sites
                # Added " · " to handle any KNOWN_SITES misses with middle dots
                for sep in [" - ", " – ", " | ", " · "]:
                    if sep in clean:
                        return f"Chrome: {clean.split(sep)[-1].strip()}"

                # No separator at all — use the whole remaining string
                return f"Chrome: {clean}"

            # For every other known app (VS Code, Slack, DBeaver, etc.)
            return app_name

    # ── Fallback for unknown apps ─────────────────────────────────────────────
    for separator in [" - ", " – ", " | ", " · "]:
        if separator in title:
            return title.split(separator)[-1].strip()

    return title[:40]

# get_chrome_tab() has been fully removed.
# We no longer need CDP (Chrome DevTools Protocol) because the window title
# already contains the website name. pygetwindow gives us everything we need.


def get_active_window() -> tuple[Optional[str], Optional[str]]:
    """
    Asks the operating system: "what window is the user looking at right now?"
    Returns two things: the clean app name and the raw window title.
    Example return: ("Chrome: YouTube", "Master Linux... - YouTube - Google Chrome")
    """
    try:
        # Ask the OS which window is currently in focus (on top of the screen).
        win = gw.getActiveWindow()

        # If the user has no window focused (e.g. clicked the desktop),
        # or the window has no title, there's nothing to track — return nothing.
        if not win or not win.title.strip():
            return None, None

        # Get the raw window title exactly as the OS sees it.
        # e.g. "Chat - Claude - Google Chrome"
        title = win.title.strip()

        # Pass the raw title through classify_app() to get a clean, human-readable name.
        # e.g. "Chat - Claude - Google Chrome" → "Chrome: Claude"
        app_name = classify_app(title)

        # Return both: the clean name (used as the label in the DB) and
        # the full raw title (stored for reference so you can see exact details later).
        return app_name, title

    except Exception as e:
        # If anything goes wrong reading the window (rare OS-level errors),
        # log it quietly as a debug message and return nothing rather than crashing.
        log.debug(f"Could not read active window: {e}")
        return None, None


# ── Junk filter ───────────────────────────────────────────────────────────────
# Any app_name that matches something in this set will be silently ignored.
# It will never be logged and never written to the database.
# Add to this list whenever you notice new junk appearing in your daily_stats.
IGNORED_APPS = {
    # ── Windows UI noise ─────────────────────────────────────────────────────
    "Windows Default Lock Screen",  # screen lock — not real activity
    "Task Switching",               # Alt+Tab overlay
    "Start",                        # Windows Start menu
    "Search",                       # Windows Search overlay
    "Taskbar",                      # Windows taskbar
    "Desktop",                      # clicking the desktop
    "Program Manager",              # Windows shell background process
    "Programs",
    "Jump List for Sticky Notes",
    "Save As",
    "Action Center",                   # Windows notifications sidebar
    "Volume Mixer",                    # Windows volume control popup
    "Unable to terminate processes",  # Windows "Close Programs" popup when shutting down
    "Microsoft Teams Sharing",         # The "You are sharing your screen" notification from Teams
    "Reload site?",
    "UnlockingWindow",
    "Task Manager",
    "Network Connections",
    "Volume Control",
    "Windows Security",                # The "Windows Security" popup that appears when UAC prompts
    "Avast Free Antivirus", 
    "Network Connections",
    "'Windows Default Lock Screen','Search','Start','Task Switching','UnlockingWindow' ,'Task Manager', 'Volume Control', 'Avast Free Antivirus', 'Action center', 'Reload site?'"
    "Network Connections",
    
    # ── Chrome junk tabs ─────────────────────────────────────────────────────
    "Chrome: New Tab",              # blank new tab, not real activity
    "Chrome: Untitled",             # tab still loading
    "Chrome: Sign in to your account",  # Google sign-in popup

    # ── DBeaver table name bleed ─────────────────────────────────────────────
    # These appear when DBeaver is open and the table name leaks into the title
    # Now fixed by adding DBeaver to KNOWN_APPS, but keeping here as safety net
    "public",
    "daily_stats",
    "sessions",
    "productivity_tracker",

    # ── Other noise ──────────────────────────────────────────────────────────
    "Activity Tracker",             # our own script window — don't track ourselves
    "gemini.google.com",            # raw domain bleed before classify_app catches it
}


# ── Main loop ─────────────────────────────────────────────────────────────────

# Path to the lock file. Only one running instance of this script can hold this file.
# Stored in the same folder as the script itself.
LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tracker.lock")

def acquire_lock() -> None:
    """
    Prevents multiple instances of the tracker from running simultaneously.
    Uses psutil for cross-platform process checking since os.kill(pid, 0)
    does not work correctly on Windows.
    """
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                old_pid = int(f.read().strip())

            # ── FIXED: use psutil instead of os.kill — works on Windows and Linux ──
            # psutil.pid_exists() checks if a process with that PID is alive
            # without needing to send a signal (which Windows doesn't support)
            import psutil
            if psutil.pid_exists(old_pid):
                log.error(
                    f"Another instance is already running (PID {old_pid}). "
                    f"If you're sure it's dead, delete {LOCK_FILE} and try again."
                )
                sys.exit(1)
            else:
                # PID in lock file is dead — stale lock from a crash or force-kill
                log.warning("Stale lock file found — previous instance did not shut down cleanly. Overwriting.")

        except (ValueError, OSError):
            # File was corrupted or unreadable — safe to overwrite
            log.warning("Lock file unreadable — overwriting.")

    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    log.debug(f"Lock acquired (PID {os.getpid()}) → {LOCK_FILE}")

def release_lock() -> None:
    """
    Deletes the lock file when the script exits cleanly.
    Called from shutdown() so the next run starts fresh.
    """
    try:
        os.remove(LOCK_FILE)
        log.debug("Lock released.")
    except FileNotFoundError:
        pass  # already gone, no problem


def run():
    """
    The heart of the tracker. Connects to the database, then watches your screen
    every 2 seconds. Every time you switch windows, it saves the old session and
    starts a new one. Runs forever until you press Ctrl+C.
    """

    # ── Ghost script prevention ───────────────────────────────────────────────
    # Must be the very first thing we do — before any DB connection or logging.
    # If another instance is running, this call will exit immediately.
    acquire_lock()
    
    # ── NEW: Ensure AWS allows our IP before connecting ─────────────────────
    log.info("Checking AWS Security Group IP rules...")
    ensure_aws_access()

    log.info("Connecting to PostgreSQL...")
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    init_db(conn)

    current_app   = None
    current_title = None
    session_start = None

    def shutdown(*_):
        """
        Called automatically when you press Ctrl+C or the system sends a stop signal.
        Closes the open session, releases the lock file, and exits cleanly.
        """
        log.info("Shutting down tracker...")

        if current_app and session_start:
            close_session(conn, current_app, current_title, session_start, datetime.now(CAIRO_TZ))
            if current_app.startswith("Chrome: "):
                close_session(conn, "Google Chrome", current_title, session_start, datetime.now(CAIRO_TZ))

        conn.close()

        # ── NEW: release the lock so the next run starts cleanly ─────────────
        release_lock()

        sys.exit(0)

    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    log.info(f"Tracker is running. Checking every {POLL_INTERVAL} seconds. Press Ctrl+C to stop.")

    while True:

        # ── DB connection survival check ──────────────────────────────────────
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        except Exception as e:
            log.warning(f"Connection lost. Attempting to reconnect... Error: {e}")
            try:
                conn = psycopg2.connect(**DB_CONFIG)
                conn.autocommit = True
                log.info("Successfully reconnected to the database!")
            except Exception as reconnect_error:
                log.error(f"Reconnect failed: {reconnect_error}")
                time.sleep(POLL_INTERVAL)
                continue
        # ─────────────────────────────────────────────────────────────────────

        app, title = get_active_window()
        now = datetime.now(CAIRO_TZ)

        switched = (app != current_app or title != current_title)

        if switched:
            if current_app and session_start:
                close_session(conn, current_app, current_title, session_start, now)
                if current_app.startswith("Chrome: "):
                    close_session(conn, "Google Chrome", current_title, session_start, now)

            current_app   = app
            current_title = title
            session_start = now

            # ── NEW: ignore junk before writing anything to the database ──────
            # If the app name is in our blocklist, update memory so we don't
            # re-trigger on the next poll, but write nothing to the DB.
            if app and app not in IGNORED_APPS:
                log.info(f"[{app}] {title}")
                open_session(conn, app, title, now)
                if app.startswith("Chrome: "):
                    open_session(conn, "Google Chrome", title, now)
            elif app in IGNORED_APPS:
                # Log at debug level so you can still see it with LOG_LEVEL=DEBUG
                # but it won't clutter your normal INFO logs
                log.debug(f"[IGNORED] {app}")

        time.sleep(POLL_INTERVAL)

# ── Entry point ───────────────────────────────────────────────────────────────

# Python sets __name__ to "__main__" only when you run this file directly.
# If another script were to import this file, run() would NOT be called automatically.
# This is standard Python practice to make files both importable and runnable.
if __name__ == "__main__":
    run()