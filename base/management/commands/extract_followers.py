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
import tempfile
from dotenv import load_dotenv

load_dotenv()

# Support for headless control from .env
HEADLESS_MODE = os.getenv("HEADLESS", "false").lower() == "true"

class InstagramFollowers:
    def __init__(self, time_sleep: int = 10, user=None) -> None:
        self.time_sleep = time_sleep
        self.user = user  # Firebase UID (str)
        self.existing_followers = {}
        self.found_usernames = set()
        self.success = False

        environment = os.getenv("ENVIRONMENT", "local")
        headless = os.getenv("HEADLESS", "false").lower() == "true"
        chrome_bin_path = os.getenv("CHROME_BIN", "")

        options = uc.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-notifications")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        if environment == "production" and chrome_bin_path:
            options.binary_location = chrome_bin_path
        elif environment == "local":
            # On Windows, path to Chrome
            options.binary_location = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

        print("🌍 ENV:", environment)
        print("🔥 Headless mode:", headless)
        print("🧠 Chromium binary at:", options.binary_location)

        # ✅ Use version 4 syntax (no executable_path needed)
        self.webdriver = uc.Chrome(options=options, use_subprocess=True)

    def open_instagram(self):
        self.webdriver.get("https://www.instagram.com/")
        print("🚀 Log into Instagram manually, then press ENTER here.")
        flag_path = os.path.join(tempfile.gettempdir(), f"ig_ready_user_{self.user}.flag")
        if os.path.exists(flag_path):
            os.remove(flag_path)
        while not os.path.exists(flag_path):
            time.sleep(1)

    def go_to_followers(self):
        try:
            print("🔍 Finding Followers button...")
            followers_button = WebDriverWait(self.webdriver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/followers/')]"))
            )
            followers_button.click()
            time.sleep(5)
        except Exception as e:
            print(f"⚠️ Error clicking Followers button: {str(e)}")
            self.webdriver.quit()
            exit()

    def load_existing_followers(self):
        print("📥 Loading existing followers from Firestore...")
        collection_ref = db.collection("users").document(str(self.user)).collection("followers")
        docs = collection_ref.stream()
        self.existing_followers = {
            doc.to_dict().get("username"): doc.id for doc in docs if doc.to_dict().get("username")
        }

    def scroll_and_extract(self) -> bool:
        try:
            print("📜 Scrolling and extracting followers...")
            scroll_box = WebDriverWait(self.webdriver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "xyi19xy"))
            )
            last_height = 0

            while True:
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
                    print("⏹️ Reached end of scroll.")
                    return True  # ✅ Completed successfully
                last_height = new_height

        except Exception as e:
            print(f"⚠️ Error while scrolling or extracting: {str(e)}")
            return False  # ❌ Extraction failed

    def save_results_to_db(self):
        if not self.found_usernames:
            print("❌ No followers extracted.")
            return

        print("📦 Saving results to Firestore...")
        collection_ref = db.collection("users").document(str(self.user)).collection("followers")

        before_set = set(self.existing_followers.keys())
        after_set = self.found_usernames

        to_add = after_set - before_set
        to_remove = before_set - after_set

        print(f"➕ To Add: {to_add}\n➖ To Remove: {to_remove}")

        batch = db.batch()

        for username in to_add:
            doc_ref = collection_ref.document()
            batch.set(doc_ref, {"username": username})
            print(f"✅ Queued to add: {username}")

        for username in to_remove:
            doc_id = self.existing_followers[username]
            doc_ref = collection_ref.document(doc_id)
            batch.delete(doc_ref)
            print(f"❌ Queued to remove: {username}")

        batch.commit()
        print("🎯 Batch update complete.")
        self.success = True

    def run(self):
        self.open_instagram()
        self.go_to_followers()
        self.load_existing_followers()
        scroll_success = self.scroll_and_extract()
        if scroll_success:
            self.save_results_to_db()
            self.success = True
            print("🎉 Followers extraction and sync complete.")
        else:
            print("❌ Aborted: followers were NOT saved.")

        self.webdriver.quit()
       

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
