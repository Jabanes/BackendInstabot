from django.core.management.base import BaseCommand
from base.firebase import db

class Command(BaseCommand):
    help = "Migrate non_followers, followers, and followings to use username as doc ID"

    def add_arguments(self, parser):
        parser.add_argument('user_id', type=str, help="The Firebase UID of the user")

    def handle(self, *args, **kwargs):
        user_id = kwargs['user_id']

        def migrate_collection(user_id, collection_name):
            ref = db.collection("users").document(user_id).collection(collection_name)
            docs = ref.stream()

            for doc in docs:
                data = doc.to_dict()
                username = data.get("username")

                if not username:
                    self.stdout.write(self.style.WARNING(f"⚠️ Missing username in doc {doc.id} in '{collection_name}'"))
                    continue

                if doc.id == username:
                    self.stdout.write(self.style.NOTICE(f"⏩ Skipping '{username}' — already correct ID."))
                    continue

                # Copy to new doc with correct ID
                ref.document(username).set(data)
                doc.reference.delete()
                self.stdout.write(self.style.SUCCESS(f"✅ Migrated: {doc.id} → {username} in '{collection_name}'"))

        self.stdout.write(self.style.WARNING(f"🚀 Starting migration for user {user_id}"))

        for collection in ["non_followers", "followers", "followings"]:
            self.stdout.write(self.style.NOTICE(f"\n--- Processing {collection} ---"))
            migrate_collection(user_id, collection)

        self.stdout.write(self.style.SUCCESS(f"🎉 Migration complete for user {user_id}"))