from django.core.management.base import BaseCommand
from base.firebase import db
from firebase_admin import firestore
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
from dotenv import load_dotenv

load_dotenv()

HEADLESS_MODE = os.getenv("HEADLESS", "false").lower() == "true"

class InstagramFollowing:
    def __init__(self, time_sleep: int = 10, user=None, cookies=None, profile_url=None) -> None:
        self.time_sleep = time_sleep
        self.user = user  # Firebase UID (str)
        self.following = set()
        self.existing_following = {}
        self.success = False
        self.cookies = cookies or []
        self.profile_url = profile_url


        environment = os.getenv("ENVIRONMENT", "local")
        headless = os.getenv("HEADLESS", "false").lower() == "true"
        chrome_bin_path = os.getenv("CHROME_BIN", "")
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

        chrome_options = uc.ChromeOptions()

        if headless:
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
        print("🔥 Headless mode:", headless)
        print("🧠 Chromium binary at:", chrome_options.binary_location)


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
            raise e

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

            return True  # ✅ Completed successfully
        
        except Exception as e:
            print(f"❌ Fatal error during scrolling: {str(e)}")
            raise e  # <- this is key!

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
        try:
            self.open_instagram()
            self.go_to_following()
            self.load_existing_following()

            scroll_success = self.scroll_and_extract()
            if scroll_success:
                self.save_results_to_db()
                self.success = True
                print("🎉 Following extraction and sync complete.")
            else:
                print("❌ Scrolling failed — aborting save.")
                self.success = False

        except Exception as e:
            print(f"❌ Bot failed during run(): {str(e)}")
            self.success = False
            raise

        finally:
            try:
                self.webdriver.quit()
            except Exception as e:
                print(f"⚠️ Failed to quit webdriver: {e}")


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
