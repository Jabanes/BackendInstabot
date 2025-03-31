import os
import tempfile
import sys

user_id = sys.argv[1]
flag_path = os.path.join(tempfile.gettempdir(), f"new_data_flag_user_{user_id}.flag")
with open(flag_path, "w") as f:
    f.write("new_data")

print(f"✅ Flag created for user {user_id}")
