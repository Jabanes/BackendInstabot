from django.core.management.base import BaseCommand
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

HEADLESS_MODE = os.getenv("HEADLESS", "false").lower() == "true"

class InstagramFollowing:
    def __init__(self, time_sleep: int = 10, user=None) -> None:
        self.time_sleep = time_sleep
        self.user = user  # Firebase UID (str)
        self.following = set()
        self.existing_following = {}
        self.success = False

        options = uc.ChromeOptions()
        options.headless = HEADLESS_MODE
        options.add_argument("--disable-notifications")

        # 🔥 For debugging (optional, if you want to confirm headless mode)
        print("🔥 Running in headless mode:", HEADLESS_MODE)

        # ✅ Let undetected_chromedriver use its built-in Chromium
        self.webdriver = uc.Chrome(options=options)


    def open_instagram(self):
        self.webdriver.get("https://www.instagram.com/")
        print("🚀 Log into Instagram manually, then press ENTER here.")
        flag_path = os.path.join(tempfile.gettempdir(), f"ig_ready_user_{self.user}.flag")
        if os.path.exists(flag_path):
            os.remove(flag_path)
        while not os.path.exists(flag_path):
            time.sleep(1)

    def go_to_following(self):
        try:
            print("🔍 Finding Following button...")
            following_button = WebDriverWait(self.webdriver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/following/')]"))
            )
            following_button.click()
            time.sleep(5)
        except Exception as e:
            print(f"⚠️ Error clicking Following button: {str(e)}")
            self.webdriver.quit()
            exit()

    def load_existing_following(self):
        print("📥 Loading existing following from Firestore...")
        collection_ref = db.collection("users").document(str(self.user)).collection("followings")
        docs = collection_ref.stream()
        self.existing_following = {
            doc.to_dict().get("username"): doc.id for doc in docs if doc.to_dict().get("username")
        }

    def scroll_and_extract(self):
        try:
            print("📜 Scrolling and extracting ONLY valid Following users...")
            scroll_box = WebDriverWait(self.webdriver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "xyi19xy"))
            )
            last_height = 0

            while True:
                user_blocks = scroll_box.find_elements(
                    By.XPATH,
                    ".//div[contains(@class, 'x1yztbdb') or contains(@class, 'x1qjc9v5')]"
                )

                for block in user_blocks:
                    try:
                        username_elem = block.find_element(
                            By.XPATH, ".//span[@class='_ap3a _aaco _aacw _aacx _aad7 _aade']"
                        )
                        button_elem = block.find_element(
                            By.XPATH, ".//div[@class='_ap3a _aaco _aacw _aad6 _aade' and text()='Following']"
                        )

                        if username_elem and button_elem:
                            username = username_elem.text.strip()
                            if username:
                                self.following.add(username)
                    except Exception:
                        continue

                self.webdriver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scroll_box)
                time.sleep(5)
                new_height = self.webdriver.execute_script("return arguments[0].scrollTop", scroll_box)

                if new_height == last_height:
                    print("⏹️ Reached end of scroll.")
                    break
                last_height = new_height

        except Exception as e:
            print(f"⚠️ Error while scrolling or extracting: {str(e)}")

    def save_results_to_db(self):
        if not self.user or not self.following:
            print(f"❌ No following extracted for {self.user}.")
            return

        print(f"📦 Saving results to Firestore for {self.user}...")
        collection_ref = db.collection("users").document(str(self.user)).collection("followings")

        before_set = set(self.existing_following.keys())
        after_set = self.following

        to_add = after_set - before_set
        to_remove = before_set - after_set

        print(f"➕ To Add: {to_add}\n➖ To Remove: {to_remove}")

        batch = db.batch()

        for username in to_add:
            doc_ref = collection_ref.document()
            batch.set(doc_ref, {"username": username})
            print(f"✅ Queued to add: {username}")

        for username in to_remove:
            doc_id = self.existing_following[username]
            doc_ref = collection_ref.document(doc_id)
            batch.delete(doc_ref)
            print(f"❌ Queued to remove: {username}")

        batch.commit()
        print("🎯 Batch update complete.")
        self.success = True

    def run(self):
        self.open_instagram()
        self.go_to_following()
        self.load_existing_following()
        self.scroll_and_extract()
        self.save_results_to_db()
        print("🎉 Following extraction and sync complete.")
        self.webdriver.quit()


class Command(BaseCommand):
    help = "Extract following and save them in Firestore"

    def add_arguments(self, parser):
        parser.add_argument('user_id', type=str)

    def handle(self, *args, **kwargs):
        user_id = kwargs['user_id']
        bot = InstagramFollowing(user=user_id)
        bot.run()

        if bot.success:
            self.stdout.write(self.style.SUCCESS(f"✅ Successfully saved following for user {user_id}"))
        else:
            self.stdout.write(self.style.ERROR(f"❌ No data extracted for user {user_id}"))
