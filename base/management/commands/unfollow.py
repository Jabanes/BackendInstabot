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
        chrome_bin_path = os.getenv("CHROME_BIN", "")
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

        chrome_options = uc.ChromeOptions()

        if HEADLESS_MODE:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        # Decide which binary path to use
        if environment == "production" and chrome_bin_path:
            chrome_options.binary_location = chrome_bin_path
            browser_path = chrome_bin_path
        else:
            chrome_options.binary_location = chrome_path
            browser_path = chrome_path

        # ✅ Instantiate webdriver only ONCE
        self.webdriver = uc.Chrome(
            options=chrome_options,
            browser_executable_path=browser_path,
            use_subprocess=True
        )

        print("🌍 ENV:", environment)
        print("🔥 Headless mode:", HEADLESS_MODE)
        print("🧠 Chromium binary at:", chrome_options.binary_location)

    def wait(self):
        time.sleep(random.uniform(2, 5))

    def load_non_followers(self):
        return [n['username'] for n in NonFollowerStore.list(self.user)]

    def open_instagram(self):
        try:
            self.webdriver.get("https://www.instagram.com/")
            self.webdriver.delete_all_cookies()
            for cookie in self.cookies:
                cookie.pop("sameSite", None)
                cookie.pop("hostOnly", None)
                cookie["domain"] = ".instagram.com"
                self.webdriver.add_cookie(cookie)
            self.webdriver.get(self.profile_url)
            time.sleep(5)
        except Exception as e:
            print(f"❌ open_instagram failed: {e}")
            raise e

    def unfollow_user(self, username):
        try:
            self.webdriver.get(f"https://www.instagram.com/{username}/")
            self.wait()

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
        try:
            self.open_instagram()

            usernames = self.load_non_followers()
            if not usernames:
                print("⚠️ No non-followers found. Exiting.")
                self.success = False
                return

            for username in usernames:
                try:
                    if self.unfollow_user(username):
                        self.unfollowed.append(username)
                except Exception as e:
                    print(f"⚠️ Error unfollowing {username}: {e}")
                    continue  # Move to next user instead of breaking the loop

            self.save_results_to_db()

        except Exception as e:
            print(f"❌ Unfollow bot error: {e}")
            self.success = False
            raise  # Make sure the view catches it and responds with error

        finally:
            try:
                self.webdriver.quit()
            except Exception as e:
                print(f"⚠️ Failed to quit webdriver: {e}")

