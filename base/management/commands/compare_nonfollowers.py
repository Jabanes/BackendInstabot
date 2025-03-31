from django.core.management.base import BaseCommand
from base.firebase_stores import FollowerStore, FollowingStore, NonFollowerStore
from base.firebase import db
import os
import tempfile

class Command(BaseCommand):
    help = "Find users who don’t follow back and save in Firebase"

    def add_arguments(self, parser):
        parser.add_argument('user_id', type=str, help="The UID of the Firebase user")

    def handle(self, *args, **kwargs):
        user_id = kwargs['user_id']

        # Fetch followers and followings
        followers = set(f["username"] for f in FollowerStore.list(user_id))
        followings = set(f["username"] for f in FollowingStore.list(user_id))

        if not followers or not followings:
            self.stdout.write(self.style.WARNING("⚠️ No followers or followings found for this user."))
            return

        non_followers = sorted(followings - followers)

        # Clear previous non-followers
        NonFollowerStore.clear(user_id)

        # Save updated non-followers
        for username in non_followers:
            NonFollowerStore.add(user_id, username)

        # Create flag for frontend
        flag_path = os.path.join(tempfile.gettempdir(), f"new_data_flag_user_{user_id}.flag")
        with open(flag_path, "w") as f:
            f.write("new_data")

        self.stdout.write(self.style.SUCCESS(
            f"✅ Found {len(non_followers)} non-followers. Saved to Firebase for user {user_id}."
        ))