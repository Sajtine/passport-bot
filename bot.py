from playwright.sync_api import sync_playwright, TimeoutError
from datetime import datetime
import pytz
import requests
import os


# ================= TELEGRAM CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")


def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        requests.post(url, data=payload)
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

    # CURRENT MONTH
    current_month = get_month_name(page)
    print(f"📍 Current Month: {current_month}")

    if check_availability(page):
        msg = f"🎉 SLOT FOUND in CURRENT MONTH!\n📅 {current_month}"
        print(msg)

        page.screenshot(path="slot_current.png")
        send_telegram(msg)
        return True

    print("❌ No slots in current month")

    # NEXT MONTH
    next_btn = page.locator(".next").first

    if next_btn.count() == 0:
        print("❌ Next month button not found")
        return False

    try:
        next_btn.click(force=True)
        page.wait_for_timeout(2000)
    except Exception as e:
        print(f"Click error: {e}")
        return False

    next_month = get_month_name(page)
    print(f"\n📍 Next Month: {next_month}")

    if check_availability(page):
        msg = f"🎉 SLOT FOUND in NEXT MONTH!\n📅 {next_month}"
        print(msg)

        page.screenshot(path="slot_next.png")
        send_telegram(msg)
        return True

    print("❌ No slots in next month")
    return False


# ================= MAIN BOT =================
def run_bot():
    if not is_within_time_window():
        print("⏳ Outside time window")
        return

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

        # test working bot
        send_telegram("✅ TEST: Bot successfully reached schedule page")

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

        scan_current_and_next_month(page)

        context.close()
        browser.close()


# ================= ENTRY POINT =================
if __name__ == "__main__":
    run_bot()   