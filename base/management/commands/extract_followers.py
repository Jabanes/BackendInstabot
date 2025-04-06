from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from base.firebase import db
from firebase_admin import firestore
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
from dotenv import load_dotenv
import sys

load_dotenv()

# Support for headless control from .env
HEADLESS_MODE = os.getenv("HEADLESS", "false").lower() == "true"

from pathlib import Path

class InstagramFollowers:
    def __init__(self, time_sleep: int = 10, user=None, cookies=None, profile_url=None) -> None:
        self.time_sleep = time_sleep
        self.user = user  # Firebase UID
        self.cookies = cookies or []
        self.profile_url = profile_url
        self.existing_followers = {}
        self.found_usernames = set()
        self.success = False

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

        print("🌍 ENV:", environment, flush=True)
        print("🔥 Headless mode:", HEADLESS_MODE, flush=True)
        print("🧠 Chromium binary at:", chrome_options.binary_location, flush=True)

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
            print(f"❌ open_instagram failed: {e}", flush=True)
            raise e

    def load_existing_followers(self):
        print("📥 Loading existing followers from Firestore...", flush=True)
        collection_ref = db.collection("users").document(str(self.user)).collection("followers")
        docs = collection_ref.stream()
        self.existing_followers = {
            doc.to_dict().get("username"): doc.id for doc in docs if doc.to_dict().get("username")
        }

    def go_to_followers(self):
        try:
            print("🔍 Finding Followers button...", flush=True)
            followers_button = WebDriverWait(self.webdriver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/followers/')]"))
            )
            followers_button.click()
            time.sleep(5)
        except Exception as e:
            print(f"⚠️ Error clicking Followers button: {str(e)}", flush=True)
            self.webdriver.quit()
            exit()
            raise e

    def scroll_and_extract(self) -> bool:
        try:
            print("📜 Scrolling and extracting followers...", flush=True)
            scroll_box = WebDriverWait(self.webdriver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "xyi19xy"))
            )
            last_height = 0

            while True:
                print("🔄 Scrolling...", flush=True)
                sys.stdout.flush()
                elements = scroll_box.find_elements(
                    By.XPATH, ".//span[@class='_ap3a _aaco _aacw _aacx _aad7 _aade']"
                )
                for el in elements:
                    username = el.text.strip()
                    if username:
                        self.found_usernames.add(username)

                self.webdriver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scroll_box)
                time.sleep(5)
                new_height = self.webdriver.execute_script("return arguments[0].scrollTop", scroll_box)
                if new_height == last_height:
                    print("⏹️ Reached end of scroll.", flush=True)
                    break
                last_height = new_height

            return True  # ✅ Completed successfully      

        except Exception as e:
            print(f"❌ Error in scroll_and_extract: {e}", flush=True)
            raise e

    def save_results_to_db(self):
        if not self.found_usernames:
            print("❌ No followers extracted.", flush=True)
            return

        print("📦 Saving results to Firestore...", flush=True)
        collection_ref = db.collection("users").document(str(self.user)).collection("followers")

        before_set = set(self.existing_followers.keys())
        after_set = self.found_usernames

        to_add = after_set - before_set
        to_remove = before_set - after_set

        print(f"➕ To Add: {to_add}\n➖ To Remove: {to_remove}", flush=True)

        batch = db.batch()

        for username in to_add:
            doc_ref = collection_ref.document()
            batch.set(doc_ref, {"username": username})
            print(f"✅ Queued to add: {username}", flush=True)
            sys.stdout.flush()

        for username in to_remove:
            doc_id = self.existing_followers[username]
            doc_ref = collection_ref.document(doc_id)
            batch.delete(doc_ref)
            print(f"❌ Queued to remove: {username}", flush=True)
            sys.stdout.flush()

        batch.commit()
        print("🎯 Batch update complete.", flush=True)
        self.success = True

    def run(self):
        try:
            self.open_instagram()
            self.go_to_followers()
            self.load_existing_followers()

            scroll_success = self.scroll_and_extract()
            if scroll_success:
                self.save_results_to_db()
                self.success = True
                print("🎉 Followers extraction and sync complete.", flush=True)
            else:
                print("❌ Aborted: followers were NOT saved.", flush=True)
                self.success = False

        except Exception as e:
            print(f"❌ Followers bot error: {str(e)}", flush=True)
            self.success = False
            raise

        finally:
            try:
                self.webdriver.quit()
            except Exception as e:
                print(f"⚠️ Failed to quit webdriver: {e}", flush=True)


class Command(BaseCommand):
    help = "Extract followers and save them in Firestore"

    def add_arguments(self, parser):
        parser.add_argument('user_id', type=str)

    def handle(self, *args, **kwargs):
        user_id = kwargs['user_id']

        bot = InstagramFollowers(user=user_id)
        bot.run()

        if bot.success:
            self.stdout.write(self.style.SUCCESS(f"✅ Successfully saved followers for user {user_id}"))
        else:
            self.stdout.write(self.style.ERROR(f"❌ No data extracted for user {user_id}"))
