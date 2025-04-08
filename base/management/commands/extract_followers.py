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
from selenium.common.exceptions import StaleElementReferenceException

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
        self.seen_usernames_all = set()  # 🧠 For deletion tracking


        environment = os.getenv("ENVIRONMENT", "local")
        chrome_bin_path = os.getenv("CHROME_BIN", "")
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

        chrome_options = uc.ChromeOptions()

        if HEADLESS_MODE:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--window-size=1280,800") 
        # chrome_options.add_argument("--single-process")
        chrome_options.add_argument("--remote-debugging-port=9222")
        chrome_options.add_argument("--blink-settings=imagesEnabled=false") 
        chrome_options.add_argument("--disable-background-networking")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-client-side-phishing-detection")
        chrome_options.add_argument("--disable-default-apps")
        chrome_options.add_argument("--disable-sync")
        chrome_options.add_argument("--metrics-recording-only")
        chrome_options.add_argument("--no-first-run")
        chrome_options.add_argument("--disable-hang-monitor")
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_argument("--disable-prompt-on-repost")



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
            raise e

    def scroll_and_extract(self) -> bool:
        try:
            print("📜 Scrolling and extracting followers...", flush=True)
            scroll_box = WebDriverWait(self.webdriver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "xyi19xy"))
            )

            last_height = self.webdriver.execute_script("return arguments[0].scrollHeight", scroll_box)
            seen_usernames = set()
            scroll_attempts = 0

            while True:
                time.sleep(2)
                elements = scroll_box.find_elements(
                    By.XPATH, ".//span[@class='_ap3a _aaco _aacw _aacx _aad7 _aade']"
                )
                current_chunk = set()

                for i in range(len(elements)):
                    retry_attempts = 2
                    while retry_attempts > 0:
                        try:
                            el = elements[i]
                            username = el.text.strip()
                            if username and username not in seen_usernames:
                                current_chunk.add(username)
                                seen_usernames.add(username)
                                self.seen_usernames_all.add(username)
                            break
                        except StaleElementReferenceException:
                            elements = scroll_box.find_elements(
                                By.XPATH, ".//span[@class='_ap3a _aaco _aacw _aacx _aad7 _aade']"
                            )
                            retry_attempts -= 1
                            time.sleep(1)

                if current_chunk:
                    self.process_chunk(current_chunk)

                self.webdriver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scroll_box)
                time.sleep(2)

                new_height = self.webdriver.execute_script("return arguments[0].scrollHeight", scroll_box)
                if new_height == last_height:
                    scroll_attempts += 1
                    if scroll_attempts > 2:
                        print("⏹️ Reached end of scroll.", flush=True)
                        break
                else:
                    scroll_attempts = 0
                    last_height = new_height

            return True

        except Exception as e:
            print(f"❌ Error in scroll_and_extract: {e}", flush=True)
            raise e



    def process_chunk(self, chunk):
        collection_ref = db.collection("users").document(str(self.user)).collection("followers")
        new_users = chunk - set(self.existing_followers.keys())

        if not new_users:
            return

        print(f"📦 Saving {len(new_users)} new followers...", flush=True)
        batch = db.batch()
        for username in new_users:
            doc_ref = collection_ref.document()
            batch.set(doc_ref, {"username": username})
            print(f"✅ Queued to add: {username}", flush=True)
            self.existing_followers[username] = doc_ref.id  # Add to local cache

        batch.commit()
        print("📬 Chunk committed to Firestore.", flush=True)


    def save_removed_users_to_db(self):
        collection_ref = db.collection("users").document(str(self.user)).collection("followers")
        to_remove = set(self.existing_followers.keys()) - self.seen_usernames_all

        if not to_remove:
            print("✅ No followers to remove.", flush=True)
            return

        print(f"➖ To Remove: {to_remove}", flush=True)
        batch = db.batch()

        for username in to_remove:
            doc_id = self.existing_followers.get(username)
            if doc_id:
                doc_ref = collection_ref.document(doc_id)
                batch.delete(doc_ref)
                print(f"❌ Queued to remove: {username}", flush=True)

        batch.commit()
        print("🎯 Removed unfollowed users from Firestore.", flush=True)
        

    def run(self):
        try:
            self.open_instagram()
            self.go_to_followers()
            self.load_existing_followers()

            scroll_success = self.scroll_and_extract()
            if scroll_success:
                self.save_removed_users_to_db()
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
