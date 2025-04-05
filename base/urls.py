from django.urls import path
from .firebase_views import check_new_data_flag, generateNonFollowersList, get_non_followers, get_user_follow_stats, login, run_instagram_followers_script, run_unfollow_non_followers_script, update_non_followers_list, update_profile, run_instagram_following_script

from . import firebase_views
urlpatterns = [
    path('register',firebase_views.signUp),
    path('login/', login, name='firebase_login'),  
    path("non-followers", get_non_followers, name="get_non_followers"),
    path("non-followers/compare", generateNonFollowersList),
    path("non-followers/update-list", update_non_followers_list, name="update_non_followers_list"),
    path('update-profile', update_profile, name='update_profile'),
    path('get-following', run_instagram_following_script, name='run-following-script'),
    path('get-followers', run_instagram_followers_script),
    path('unfollow', run_unfollow_non_followers_script, name='run_unfollow_non_followers'),
    path('follow-stats', get_user_follow_stats),
    path('check-data', check_new_data_flag),

    
]
