from playwright.sync_api import sync_playwright, TimeoutError
from datetime import datetime
import pytz
import time


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


# ================= AVAILABILITY CHECK =================
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


# ================= SCAN CURRENT + NEXT MONTH =================
def scan_current_and_next_month(page):
    print("\n📅 Starting 2-month scan...\n")

    page.wait_for_timeout(1500)

    # -------- CURRENT MONTH --------
    current_month = get_month_name(page)
    print(f"📍 Current Month: {current_month}")

    if check_availability(page):
        print("🎉 SLOT AVAILABLE in CURRENT MONTH!")
        page.screenshot(path="slot_current_month.png")
        return True
    else:
        print("❌ No slots in current month")

    # -------- NEXT MONTH --------
    next_btn = page.locator(".next:visible").first

    if next_btn.count() == 0:
        print("❌ Next month button not found")
        return False

    try:
        next_btn.click(force=True)
        page.wait_for_timeout(2000)
    except Exception as e:
        print(f"❌ Failed to click next: {e}")
        return False

    next_month = get_month_name(page)
    print(f"\n📍 Next Month: {next_month}")

    if check_availability(page):
        print("🎉 SLOT AVAILABLE in NEXT MONTH!")
        page.screenshot(path="slot_next_month.png")
        return True
    else:
        print("❌ No slots in next month")

    print("\n❌ No slots found in both months.")
    return False


# ================= MAIN BOT RUN =================
def run_bot():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # STEP 1
        page.goto("https://passport.gov.ph/appointment")
        page.wait_for_load_state("networkidle")

        # STEP 2
        safe_click(page, [
            "input[type='checkbox']",
            "label:has-text('I agree')",
            "text=I Agree"
        ], force=True)

        # STEP 3
        safe_click(page, [
            "button[value='Individual']",
            "button:has-text('Start Individual Appointment')",
            "text=Start Individual Appointment"
        ])

        page.wait_for_load_state("networkidle")

        # STEP 4
        try:
            page.wait_for_selector("#SiteID", timeout=10000)
            page.select_option("#SiteID", value="22")
        except TimeoutError:
            print("Site dropdown not found")
            browser.close()
            return

        # STEP 5
        try:
            page.wait_for_selector("#co-notif-checkbox", timeout=10000)

            clicked = safe_click(page, [
                "label[for='co-notif-checkbox']",
                "div:has(#co-notif-checkbox)"
            ])

            if not clicked:
                page.evaluate("document.getElementById('co-notif-checkbox').click();")

        except TimeoutError:
            print("Notification checkbox not found")

        # STEP 6
        try:
            confirm = page.locator("input[type='checkbox']").first
            if confirm.count() > 0:
                confirm.click(force=True)
        except:
            pass

        # STEP 7
        safe_click(page, [
            "text=NEXT",
            "button:has-text('NEXT')"
        ])

        page.wait_for_load_state("networkidle")

        # STEP 8
        scan_current_and_next_month(page)

        browser.close()


# ================= CLOUD LOOP (RENDER) =================
while True:
    if is_within_time_window():
        print("\n🟢 Inside 8AM–6PM window... Running bot")

        try:
            run_bot()
        except Exception as e:
            print(f"⚠️ Error: {e}")

    else:
        print("⏳ Outside 8AM–6PM window. Sleeping...")

    time.sleep(300)  # run every 5 minutes