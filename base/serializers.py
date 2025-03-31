from django.utils import timezone
from rest_framework import serializers
from django.contrib.auth.models import User, Group
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .firebase_stores import UserScanInfoStore
import pytz

israel_tz = pytz.timezone("Asia/Jerusalem")

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)


    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'first_name', 'last_name']


    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        group, created = Group.objects.get_or_create(name="User")
        user.groups.add(group)
        UserScanInfoStore.objects.get_or_create(user=user)
        return user


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user  # Get authenticated user
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])

        # Add user details to the token response
        data["user"] = {
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "date_joined": timezone.localtime(user.date_joined, israel_tz).strftime("%d/%m/%Y %H:%M:%S"),
            "last_login": timezone.localtime(user.last_login, israel_tz).strftime("%d/%m/%Y %H:%M:%S") if user.last_login else None,
            "roles": list(user.groups.values_list("name", flat=True)),  # Get roles as a list
        }

        return data
    

class UserUpdateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password']

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance