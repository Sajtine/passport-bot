from playwright.sync_api import sync_playwright, TimeoutError
from datetime import datetime
import pytz
import requests
import os
import json


# ================= TELEGRAM CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# ================= STATE MANAGEMENT =================
STATE_FILE = "state.json"

def load_state():
    if not os.path.exists(STATE_FILE):
        return {
            "last_result": {
                "current": False,
                "next": False
            }
        }

    with open(STATE_FILE, "r") as f:
        return json.load(f)


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }

        response = requests.post(url, data=payload)

        print("Telegram status code:", response.status_code)
        print("Telegram response:", response.text)

        if response.status_code != 200:
            print("❌ Telegram message failed!")

    except Exception as e:
        print(f"Telegram error: {e}")


# ================= TIME WINDOW =================
def is_within_time_window():
    tz = pytz.timezone("Asia/Manila")
    now = datetime.now(tz)
    return 8 <= now.hour < 18


# ================= SAFE CLICK =================
def safe_click(page, selectors, force=False):
    for sel in selectors:
        try:
            locator = page.locator(sel).first
            if locator.count() > 0:
                locator.click(force=force)
                return True
        except:
            continue
    return False


# ================= CHECK AVAILABILITY =================
def check_availability(page):
    try:
        if page.locator("text=No available date").count() > 0:
            return False

        clickable_days = page.locator(
            "td:not(.disabled):not(:has-text('Fully Booked')) a, "
            "td:not(.disabled):not(.fully-booked), "
            "td.available"
        )

        return clickable_days.count() > 0
    except:
        return False


# ================= MONTH NAME =================
def get_month_name(page):
    try:
        header = page.locator(
            ".ui-datepicker-title, .calendar-title, .month-title, .datepicker-switch"
        ).first

        if header.count() > 0:
            return header.inner_text().strip()

        return "Unknown Month"
    except:
        return "Unknown Month"


# ================= SCAN MONTHS =================
def scan_current_and_next_month(page):
    print("\n📅 Checking schedule...\n")

    # ================= CURRENT MONTH =================
    current_month = get_month_name(page)
    print(f"📍 Current Month: {current_month}")

    current_available = check_availability(page)

    if current_available:
        print("🎉 Slot found in current month")
        page.screenshot(path="slot_current.png")
    else:
        print("❌ No slots in current month")

    # ================= NEXT MONTH =================
    next_btn = page.locator(".next").first

    if next_btn.count() == 0:
        print("❌ Next month button not found")
        return current_month, current_available, "N/A", False

    try:
        next_btn.click(force=True)
        page.wait_for_timeout(2000)
    except Exception as e:
        print(f"Click error: {e}")
        return current_month, current_available, "N/A", False

    next_month = get_month_name(page)
    print(f"\n📍 Next Month: {next_month}")

    next_available = check_availability(page)

    if next_available:
        print("🎉 Slot found in next month")
        page.screenshot(path="slot_next.png")
    else:
        print("❌ No slots in next month")

    return current_month, current_available, next_month, next_available


# ================= MAIN BOT =================
def run_bot():
    # if not is_within_time_window():
    #     print("⏳ Outside time window")
    #     return

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )

        context = browser.new_context(
            locale="en-PH",
            timezone_id="Asia/Manila"
        )

        page = context.new_page()

        page.goto("https://passport.gov.ph/appointment")
        page.wait_for_load_state("networkidle")

        # Agree
        safe_click(page, [
            "input[type='checkbox']",
            "label:has-text('I agree')",
            "text=I Agree"
        ], force=True)

        # Start
        safe_click(page, [
            "button[value='Individual']",
            "button:has-text('Start Individual Appointment')"
        ])

        page.wait_for_load_state("networkidle")


        # Site
        try:
            page.wait_for_selector("#SiteID", timeout=10000)
            page.select_option("#SiteID", value="22")
        except TimeoutError:
            print("Site not found")
            return

        # Notification
        try:
            page.wait_for_selector("#co-notif-checkbox", timeout=10000)
            safe_click(page, ["label[for='co-notif-checkbox']"])
        except:
            pass

        # Confirm
        try:
            page.locator("input[type='checkbox']").first.click(force=True)
        except:
            pass

        # NEXT
        safe_click(page, ["text=NEXT", "button:has-text('NEXT')"])

        page.wait_for_load_state("networkidle")

        # Send report if there's a change
        current_month, current_available, next_month, next_available = scan_current_and_next_month(page)
        
        state = load_state()
        last = state.get("last_result", {"current": False, "next": False})

        messages = []

        # Detect CURRENT month change
        if current_available != last.get("current"):
            if current_available:
                messages.append(f"🎉 SLOT OPENED in CURRENT MONTH\n📅 {current_month}")
            else:
                messages.append(f"⚠️ SLOT CLOSED in CURRENT MONTH\n📅 {current_month}")

        # Detect NEXT month change
        if next_available != last.get("next"):
            if next_available:
                messages.append(f"🎉 SLOT OPENED in NEXT MONTH\n📅 {next_month}")
            else:
                messages.append(f"⚠️ SLOT CLOSED in NEXT MONTH\n📅 {next_month}")

        # Send only if something changed
        if messages:
            report = "📅 PASSPORT CHECK UPDATE\n\n" + "\n\n".join(messages)
            send_telegram(report)

            # save new state
            state["last_result"] = {
                "current": current_available,
                "next": next_available
            }
            save_state(state)

            print("📤 Change detected → Telegram sent")
        else:
            print("🟡 No change → no message sent")

        context.close()
        browser.close()


# ================= ENTRY POINT =================
if __name__ == "__main__":
    run_bot()   