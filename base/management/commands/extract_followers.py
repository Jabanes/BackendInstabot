from django.core.management.base import BaseCommand
from base.firebase import db
import requests
import json
from urllib.parse import urlparse

class InstagramFollowers:
    def __init__(self, time_sleep: int = 10, user=None, cookies=None, profile_url=None) -> None:
        self.time_sleep = time_sleep
        self.user = user
        self.cookies = cookies or []
        self.profile_url = profile_url
        self.existing_followers = {}
        self.seen_usernames_all = set()
        self.success = False

    def extract_username_from_url(self):
        parsed = urlparse(self.profile_url)
        path = parsed.path.strip("/").split("/")
        return path[0] if path else None

    def load_existing_followers(self):
        print("📥 Loading existing followers from Firestore...", flush=True)
        collection_ref = db.collection("users").document(str(self.user)).collection("followers")
        docs = collection_ref.stream()
        self.existing_followers = {
            doc.to_dict().get("username"): doc.id for doc in docs if doc.to_dict().get("username")
        }

    def fetch_followers(self):
        print("🔐 Setting up session with injected cookies", flush=True)
        session = requests.Session()
        for cookie in self.cookies:
            if "name" not in cookie or "value" not in cookie:
                continue
            name = cookie["name"]
            value = cookie["value"]
            domain = cookie.get("domain", ".instagram.com")
            path = cookie.get("path", "/")
            session.cookies.set(name, value, domain=domain, path=path)

        session.headers.update({
            "User-Agent": "Mozilla/5.0",
            "Accept": "*/*",
            "Referer": "https://www.instagram.com/",
            "X-CSRFToken": session.cookies.get("csrftoken", ""),
            "X-IG-App-ID": "936619743392459",
            "X-Requested-With": "XMLHttpRequest"
        })
    

        username = self.extract_username_from_url()
        print(f"🔍 Fetching user ID for {username}", flush=True)

        url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
        res = session.get(url)

        print("🧪 [DEBUG] Status Code:", res.status_code)
        print("🧪 [DEBUG] Headers:", res.headers)
        print("🧪 [DEBUG] Final URL:", res.url)

        # Parse once and store it
        try:
            data = res.json()
        except Exception as e:
            print("❌ Failed to parse JSON:", e)
            print("🧪 Fallback Text (first 500 chars):", res.text[:500])
            raise

        print("📦 User lookup response:", data)

        try:
            user_id = data["data"]["user"]["id"]
        except KeyError:
            raise Exception(f"❌ Could not extract user ID. Full response: {data}")

        followers = set()
        has_next = True
        after = None
        query_hash = "c76146de99bb02f6415203be841dd25a"

        print("📡 Querying followers via GraphQL...", flush=True)
        while has_next:
            variables = {
                "id": user_id,
                "include_reel": True,
                "fetch_mutual": False,
                "first": 50,
            }
            if after:
                variables["after"] = after

            params = {
                "query_hash": query_hash,
                "variables": json.dumps(variables)
            }

            res = session.get("https://www.instagram.com/graphql/query/", params=params)
            if res.status_code != 200:
                raise Exception(f"GraphQL query failed: {res.status_code}")

            try:
                data = res.json()
            except Exception as e:
                raise Exception(f"Failed to parse GraphQL response: {e}\nRaw: {res.text[:300]}")

                

            edges = data["data"]["user"]["edge_followed_by"]["edges"]
            page_info = data["data"]["user"]["edge_followed_by"]["page_info"]

            for edge in edges:
                username = edge["node"]["username"]
                followers.add(username)
                self.seen_usernames_all.add(username)
                print(f"➕ {username}", flush=True)

            has_next = page_info["has_next_page"]
            after = page_info["end_cursor"] if has_next else None

        return followers

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
            self.existing_followers[username] = doc_ref.id

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
            self.load_existing_followers()
            followers = self.fetch_followers()
            self.process_chunk(followers)
            self.save_removed_users_to_db()
            self.success = True
            print("🎉 Followers extraction and sync complete.", flush=True)
        except Exception as e:
            print(f"❌ Followers bot error: {str(e)}", flush=True)
            self.success = False
            raise


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
