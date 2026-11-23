"""Serializers for authentication and profile management."""
from django.contrib.auth import password_validation
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Profile, User
from .services import AuthService


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8, style={"input_type": "password"})
    password2 = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = (
            "email", "password", "password2", "first_name", "last_name",
            "phone_number", "currency", "timezone",
        )
        extra_kwargs = {
            "first_name": {"required": False},
            "last_name": {"required": False},
            "phone_number": {"required": False},
            "currency": {"required": False},
            "timezone": {"required": False},
        }

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_currency(self, value):
        if value and len(value) != 3:
            raise serializers.ValidationError("Currency must be a 3-letter code (e.g. USD).")
        return value.upper() if value else "USD"

    def validate(self, attrs):
        if attrs.get("password") != attrs.get("password2"):
            raise serializers.ValidationError({"password2": "Passwords do not match."})
        password_validation.validate_password(attrs["password"])
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")
        password = validated_data.pop("password")
        return AuthService.register(password=password, **validated_data)


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ("bio", "avatar_url", "date_of_birth", "country")


class UserProfileSerializer(serializers.ModelSerializer):
    """Flat representation combining User + Profile, used for GET/PATCH profile."""

    full_name = serializers.CharField(source="display_name", read_only=True)
    bio = serializers.CharField(source="profile.bio", required=False, allow_blank=True)
    avatar_url = serializers.URLField(source="profile.avatar_url", required=False, allow_blank=True)
    date_of_birth = serializers.DateField(source="profile.date_of_birth", required=False, allow_null=True)
    country = serializers.CharField(source="profile.country", required=False, allow_blank=True)

    class Meta:
        model = User
        fields = (
            "id", "email", "full_name", "first_name", "last_name", "phone_number",
            "currency", "timezone", "bio", "avatar_url", "date_of_birth", "country",
            "is_verified", "date_joined",
        )
        read_only_fields = ("id", "email", "is_verified", "date_joined", "full_name")

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", {})
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if profile_data:
            profile = instance.profile
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()
        return instance


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Adds safe user details to the login response."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"] = user.email
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserProfileSerializer(self.user).data
        return data


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password2 = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password2"]:
            raise serializers.ValidationError({"new_password2": "Passwords do not match."})
        password_validation.validate_password(attrs["new_password"], self.context["request"].user)
        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user


class RefreshTokenSerializer(serializers.Serializer):
    refresh = serializers.CharField()
