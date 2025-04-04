from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework import status
import subprocess
import os
import tempfile
from .management.commands.extract_followers import InstagramFollowers
from .management.commands.extract_following import InstagramFollowing
from .management.commands.unfollow import InstagramUnfollower
from base.serializers import UserUpdateSerializer, MyTokenObtainPairSerializer, RegisterSerializer
from base.firebase_stores import NonFollowerStore, FollowerStore, FollowingStore, UserScanInfoStore, UserStore
from base.firebase import db
from firebase_admin import auth as firebase_auth
import firebase_admin
from django.utils.timezone import now
from django.core.management import call_command

@api_view(['POST'])
def login(request):
    """
    Verifies Firebase ID token and returns basic user info.
    """
    id_token = request.data.get("idToken")
    if not id_token:
        return Response({"error": "Missing Firebase ID token"}, status=400)

    try:
        decoded_token = firebase_auth.verify_id_token(id_token)
        uid = decoded_token['uid']
        email = decoded_token.get('email')

        return Response({"uid": uid, "email": email})
    except Exception as e:
        return Response({"error": str(e)}, status=401)


@api_view(['POST'])
def signUp(request):
    id_token = request.data.get("idToken")
    if not id_token:
        return Response({"error": "Missing Firebase ID token"}, status=400)

    try:
        decoded_token = firebase_auth.verify_id_token(id_token)
        uid = decoded_token['uid']
        email = decoded_token.get('email')
        name = decoded_token.get('name', "")
        username = email.split("@")[0] if email else uid

        # ✅ Use your abstraction here
        UserStore.create(uid, email, username, name)

        return Response({"status": "success", "uid": uid, "email": email})

    except Exception as e:
        return Response({"error": str(e)}, status=401)

@api_view(["GET"])
def get_non_followers(request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return Response({"error": "Missing or invalid Authorization header"}, status=401)

    id_token = auth_header.split("Bearer ")[1]
    try:
        decoded_token = firebase_auth.verify_id_token(id_token)
        user_id = decoded_token["uid"]
    except Exception as e:
        return Response({"error": f"Invalid token: {str(e)}"}, status=401)
    """Returns the non-followers list for the authenticated user."""

    non_followers = []
    collection = db.collection("users").document(str(user_id)).collection("non_followers").stream()

    for doc in collection:
        data = doc.to_dict()
        data["id"] = doc.id  # Attach the document ID explicitly
        non_followers.append(data)

    return Response(
        {"non_followers": non_followers},
        status=status.HTTP_200_OK
    )

@api_view(["POST"])
def generateNonFollowersList(request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return Response({"error": "Missing or invalid Authorization header"}, status=401)

    id_token = auth_header.split("Bearer ")[1]
    try:
        decoded_token = firebase_auth.verify_id_token(id_token)
        user_id = decoded_token["uid"]
    except Exception as e:
        return Response({"error": f"Invalid token: {str(e)}"}, status=401)
    
    try:

        # Run your bot (same as before)
        call_command('compare_nonfollowers', str(user_id))

        # Fetch from Firebase instead of ORM
        non_followers = NonFollowerStore.list(user_id)

        flag_path = os.path.join(tempfile.gettempdir(), f"new_data_flag_user_{user_id}.flag")

        if os.path.exists(flag_path):
            os.remove(flag_path)
            return Response({"status": "Flag reset successfully."})

        return Response(
            {
                "status": "✅ Script executed via subprocess",
                "non_followers": non_followers
            },
            status=status.HTTP_200_OK
        )

    except subprocess.CalledProcessError as e:
        return Response(
            {"error": f"❌ Script execution failed: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(["POST"])
def update_non_followers_list(request):
    auth_header = request.headers.get("Authorization")
    print("🔥 Reached update_non_followers_list")
    if not auth_header or not auth_header.startswith("Bearer "):
        return Response({"error": "Missing or invalid Authorization header"}, status=401)

    id_token = auth_header.split("Bearer ")[1]
    try:
        decoded_token = firebase_auth.verify_id_token(id_token)
        user_id = decoded_token["uid"]
    except Exception as e:
        return Response({"error": f"Invalid token: {str(e)}"}, status=401)

    new_list = request.data.get("list", [])
    if not isinstance(new_list, list):
        return Response({"error": "Invalid non_followers data. Must be a list of usernames."}, status=400)

    print("Received new list:", new_list)
    collection_ref = db.collection("users").document(user_id).collection("non_followers")

    try:
        # Clear existing non-followers
        existing_docs = collection_ref.stream()
        for doc in existing_docs:
            doc.reference.delete()

        # Add the new filtered list
        for username in new_list:
            collection_ref.add({"username": username})

        return Response({"message": f"✅ Synced non-follower list with {len(new_list)} entries."})
    except Exception as e:
        return Response({"error": str(e)}, status=500)

@api_view(['GET'])
def get_user_follow_stats(request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return Response({"error": "Missing or invalid Authorization header"}, status=401)

    id_token = auth_header.split("Bearer ")[1]
    try:
        decoded_token = firebase_auth.verify_id_token(id_token)
        user_id = decoded_token["uid"]
    except Exception as e:
        return Response({"error": f"Invalid token: {str(e)}"}, status=401)
        
    followers = FollowerStore.list(user_id)
    followings = FollowingStore.list(user_id)
    scan_info = UserScanInfoStore.get(user_id)

    return Response({
        "followers": len(followers),
        "following": len(followings),
        "last_followers_scan": scan_info.get("last_followers_scan"),
        "last_following_scan": scan_info.get("last_following_scan"),
    })

@api_view(["PUT"])
def update_profile(request):
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        return Response({"error": "Missing or invalid Authorization header"}, status=401)

    id_token = auth_header.split("Bearer ")[1]

    try:
        decoded_token = firebase_auth.verify_id_token(id_token)
        uid = decoded_token['uid']
    except Exception as e:
        return Response({"error": f"Invalid token: {str(e)}"}, status=401)

    data = request.data

    try:
        user_ref = db.collection("users").document(uid)
        user_ref.update(data)
        return Response({"message": "Profile updated successfully"})
    except Exception as e:
        return Response({"error": f"Failed to update profile: {str(e)}"}, status=400)


@api_view(["POST"])
def run_instagram_followers_script(request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return Response({"error": "Missing or invalid Authorization header"}, status=401)

    id_token = auth_header.split("Bearer ")[1]
    try:
        decoded_token = firebase_auth.verify_id_token(id_token)
        user_id = decoded_token["uid"]
    except Exception as e:
        return Response({"error": f"Invalid token: {str(e)}"}, status=401)

    # ✅ Extract cookies and profile URL from request
    cookies = request.data.get("cookies")
    profile_url = request.data.get("profile_url")

    if not cookies or not profile_url:
        return Response({"error": "Missing cookies or profile URL"}, status=400)

    before = len(FollowerStore.list(user_id))
    
    # ✅ Pass cookies and profile URL to the bot
    bot = InstagramFollowers(user=user_id, cookies=cookies, profile_url=profile_url)
    bot.run()
    
    after = len(FollowerStore.list(user_id))

    if bot.success:
        UserScanInfoStore.update(user_id, last_followers_scan=now())
        return Response({
            "status": "success",
            "before_count": before,
            "after_count": after
        })

    return Response({
        "status": "no_change",
        "before_count": before,
        "after_count": after
    })


@api_view(["POST"])
def run_unfollow_non_followers_script(request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return Response({"error": "Missing or invalid Authorization header"}, status=401)

    id_token = auth_header.split("Bearer ")[1]
    try:
        decoded_token = firebase_auth.verify_id_token(id_token)
        user_id = decoded_token["uid"]
    except Exception as e:
        return Response({"error": f"Invalid token: {str(e)}"}, status=401)

    # ✅ Extract cookies and profile URL
    cookies = request.data.get("cookies")
    profile_url = request.data.get("profile_url")

    if not cookies or not profile_url:
        return Response({"error": "Missing cookies or profile URL"}, status=400)

    non_followers_ref = db.collection("users").document(user_id).collection("non_followers")
    following_ref = db.collection("users").document(user_id).collection("followings")
    before_non_followers = len(list(non_followers_ref.stream()))
    before_following = len(list(following_ref.stream()))

    try:
        # ✅ Run with cookie injection
        bot = InstagramUnfollower(user=user_id, cookies=cookies, profile_url=profile_url)
        bot.run()

        after_non_followers = len(list(non_followers_ref.stream()))
        after_following = len(list(following_ref.stream()))

        return Response({
            "status": "success" if after_non_followers < before_non_followers else "no_change",
            "non_followers_before": before_non_followers,
            "non_followers_after": after_non_followers,
            "following_before": before_following,
            "following_after": after_following
        })
    except Exception as e:
        return Response({"status": "error", "message": f"Unfollow script failed: {str(e)}"}, status=500)
    

@api_view(["POST"])
def run_instagram_following_script(request):
    auth_header = request.headers.get("Authorization")
    print("🧠 Headers received:", request.headers)
    if not auth_header or not auth_header.startswith("Bearer "):
        return Response({"error": "Missing or invalid Authorization header"}, status=401)

    id_token = auth_header.split("Bearer ")[1]
    try:
        decoded_token = firebase_auth.verify_id_token(id_token)
        user_id = decoded_token["uid"]
    except Exception as e:
        return Response({"error": f"Invalid token: {str(e)}"}, status=401)

    cookies = request.data.get("cookies")
    profile_url = request.data.get("profile_url")

    if not cookies or not profile_url:
        return Response({"error": "Missing cookies or profile_url"}, status=400)

    before = len(FollowingStore.list(user_id))
    bot = InstagramFollowing(user=user_id, cookies=cookies, profile_url=profile_url)
    bot.run()
    after = len(FollowingStore.list(user_id))

    if bot.success:
        UserScanInfoStore.update(user_id, last_following_scan=now())
        return Response({"status": "success", "before_count": before, "after_count": after})
    return Response({"status": "no_change", "before_count": before, "after_count": after})

@api_view(["POST"])
def confirm_bot_ready(request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return Response({"error": "Missing or invalid Authorization header"}, status=401)

    id_token = auth_header.split("Bearer ")[1]
    try:
        decoded_token = firebase_auth.verify_id_token(id_token)
        user_id = decoded_token["uid"]
    except Exception as e:
        return Response({"error": f"Invalid token: {str(e)}"}, status=401)
    
    flag_path = os.path.join(tempfile.gettempdir(), f"ig_ready_user_{user_id}.flag")
    try:
        with open(flag_path, "w") as f:
            f.write("ready")
        return Response({"status": "success", "message": "Bot confirmed ready."})
    except Exception as e:
        return Response({"status": "error", "message": str(e)}, status=500)
    

@api_view(["GET"])
def check_new_data_flag(request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return Response({"error": "Missing or invalid Authorization header"}, status=401)

    id_token = auth_header.split("Bearer ")[1]
    try:
        decoded_token = firebase_auth.verify_id_token(id_token)
        user_id = decoded_token["uid"]
    except Exception as e:
        return Response({"error": f"Invalid token: {str(e)}"}, status=401)
    
    flag_path = os.path.join(tempfile.gettempdir(), f"new_data_flag_user_{user_id}.flag")
    return Response({"new_data": os.path.exists(flag_path)})
