from django.core.management.base import BaseCommand
from base.firebase_stores import NonFollowerStore, FollowingStore
from base.firebase import db
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random
import os
import tempfile
from dotenv import load_dotenv

load_dotenv()

# Read from .env: HEADLESS=true for Railway, false for local
HEADLESS_MODE = os.getenv("HEADLESS", "false").lower() == "true"


class InstagramUnfollower:
    def __init__(self, user=None, time_sleep: int = 10, cookies=None, profile_url=None):
        self.user = user
        self.time_sleep = time_sleep
        self.cookies = cookies or []
        self.profile_url = profile_url
        self.success = False
        self.unfollowed = []

        environment = os.getenv("ENVIRONMENT", "local")
        headless = os.getenv("HEADLESS", "false").lower() == "true"
        chrome_bin_path = os.getenv("CHROME_BIN", "")

        options = uc.ChromeOptions()

        if environment == "production" and chrome_bin_path:
            prod_options = uc.ChromeOptions()
            if headless:
                prod_options.add_argument("--headless=new")
            prod_options.add_argument("--disable-notifications")
            prod_options.add_argument("--no-sandbox")
            prod_options.add_argument("--disable-dev-shm-usage")
            prod_options.binary_location = chrome_bin_path

            self.webdriver = uc.Chrome(
                options=prod_options,
                browser_executable_path=chrome_bin_path,
                use_subprocess=True
            )

        elif environment == "local":
            chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            local_options = uc.ChromeOptions()
            if headless:
                local_options.add_argument("--headless=new")
            local_options.add_argument("--disable-notifications")
            local_options.add_argument("--no-sandbox")
            local_options.add_argument("--disable-dev-shm-usage")
            local_options.binary_location = chrome_path

            self.webdriver = uc.Chrome(
                options=local_options,
                browser_executable_path=chrome_path,
                use_subprocess=True
            )

        print("🌍 ENV:", environment)
        print("🔥 Headless mode:", headless)
        print("🧠 Chromium binary at:", options.binary_location)

    def wait(self):
        time.sleep(random.uniform(2, 5))

    def load_non_followers(self):
        return [n['username'] for n in NonFollowerStore.list(self.user)]

    def open_instagram(self):
        print("🌐 Opening Instagram to inject cookies...")
        self.webdriver.get("https://www.instagram.com/")
        self.webdriver.delete_all_cookies()

        for cookie in self.cookies:
            try:
                cookie.pop("sameSite", None)
                cookie.pop("hostOnly", None)
                cookie["domain"] = ".instagram.com"
                self.webdriver.add_cookie(cookie)
                print(f"🍪 Injected cookie: {cookie['name']}")
            except Exception as e:
                print(f"⚠️ Failed to inject cookie: {cookie.get('name')} – {e}")

        print("🚀 Navigating to user profile after injecting cookies...")
        self.webdriver.get(self.profile_url)
        time.sleep(5)


    def unfollow_user(self, username):
        self.webdriver.get(f"https://www.instagram.com/{username}/")
        self.wait()

        try:
            follow_button = WebDriverWait(self.webdriver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'Following')]"))
            )
            follow_button.click()
            self.wait()

            unfollow_confirm = WebDriverWait(self.webdriver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Unfollow')]"))
            )
            unfollow_confirm.click()
            self.wait()

            print(f"✅ Unfollowed {username}")
            return True

        except Exception as e:
            print(f"⚠️ Could not unfollow {username}: {str(e)}")
            return False

    def save_results_to_db(self):
        if not self.unfollowed:
            print("📭 No users were unfollowed. Nothing to update.")
            return

        for username in self.unfollowed:
            NonFollowerStore.delete(self.user, username)
            FollowingStore.delete(self.user, username)

        print(f"🗑️ Removed {len(self.unfollowed)} users from NonFollower and Following collections.")
        self.success = True

        flag_path = os.path.join(tempfile.gettempdir(), f"new_data_flag_user_{self.user}.flag")
        with open(flag_path, "w") as f:
            f.write("new_data")
        print("📌 Change detected — flag file written for frontend.")

    def run(self):
        self.open_instagram()
        usernames = self.load_non_followers()

        if not usernames:
            print("⚠️ No non-followers found. Exiting.")
            self.webdriver.quit()
            return

        for username in usernames:
            if self.unfollow_user(username):
                self.unfollowed.append(username)

        self.save_results_to_db()
        self.webdriver.quit()


class Command(BaseCommand):
    help = "Unfollow users who don’t follow back (Firebase version)"

    def add_arguments(self, parser):
        parser.add_argument('user_id', type=str, help="The Firebase UID of the user")

    def handle(self, *args, **kwargs):
        user_id = kwargs['user_id']

        bot = InstagramUnfollower(user=user_id)
        bot.run()

        if bot.success:
            self.stdout.write(self.style.SUCCESS(f"✅ Successfully unfollowed users for {user_id}"))
            print("UNFOLLOW_SUCCESS")
        else:
            self.stdout.write(self.style.WARNING(f"⚠️ No users were unfollowed for {user_id}"))
            print("NO_UNFOLLOW_NEEDED")
