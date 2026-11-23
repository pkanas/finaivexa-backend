"""Authentication and profile API views."""
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import generics, status, views
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.common.mixins import EnvelopeMixin
from apps.common.responses import api_success

from . import serializers


class RegisterView(EnvelopeMixin, generics.CreateAPIView):
    serializer_class = serializers.RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return api_success(
            data=serializers.UserProfileSerializer(user).data,
            message="Account created successfully.",
            status=status.HTTP_201_CREATED,
        )


class LoginView(EnvelopeMixin, TokenObtainPairView):
    serializer_class = serializers.CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        return api_success(data=response.data, message="Logged in successfully.")


class RefreshView(EnvelopeMixin, TokenRefreshView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        return api_success(data=response.data)


class LogoutView(views.APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=serializers.RefreshTokenSerializer,
        responses=OpenApiTypes.OBJECT,
        summary="Log out and blacklist the refresh token",
    )
    def post(self, request, *args, **kwargs):
        serializer = serializers.RefreshTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token = RefreshToken(serializer.validated_data["refresh"])
            token.blacklist()
        except Exception as exc:  # invalid / already-blacklisted token
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"refresh": "Invalid or expired refresh token."}) from exc
        response = api_success(message="Logged out successfully.")
        response.status_code = status.HTTP_205_RESET_CONTENT
        return response


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = serializers.UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(views.APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=serializers.ChangePasswordSerializer,
        responses=OpenApiTypes.OBJECT,
        summary="Change the current user's password",
    )
    def post(self, request, *args, **kwargs):
        serializer = serializers.ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return api_success(message="Password changed successfully.")
