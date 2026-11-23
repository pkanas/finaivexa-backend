from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.categories.models import Category

User = get_user_model()


class AuthenticationTests(APITestCase):
    def test_registration_creates_user_profile_and_default_categories(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "email": "new@example.com",
                "password": "StrongPass123!",
                "password2": "StrongPass123!",
                "first_name": "New",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])
        user = User.objects.get(email="new@example.com")
        self.assertTrue(user.check_password("StrongPass123!"))
        self.assertTrue(hasattr(user, "profile"))
        self.assertGreaterEqual(Category.objects.filter(user=None).count(), 10)

    def test_registration_rejects_duplicate_email_and_weak_password(self):
        payload = {"email": "dup@example.com", "password": "short", "password2": "short"}
        first = self.client.post(reverse("accounts:register"), payload, format="json")
        self.assertEqual(first.status_code, status.HTTP_400_BAD_REQUEST)
        payload.update(password="StrongPass123!", password2="StrongPass123!")
        created = self.client.post(reverse("accounts:register"), payload, format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        duplicate = self.client.post(reverse("accounts:register"), payload, format="json")
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_returns_jwt_tokens_and_user(self):
        User.objects.create_user(email="login@example.com", password="StrongPass123!")
        response = self.client.post(
            reverse("accounts:login"),
            {"email": "login@example.com", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertIn("access", data)
        self.assertIn("refresh", data)
        self.assertEqual(data["user"]["email"], "login@example.com")

    def test_login_with_wrong_password_fails(self):
        User.objects.create_user(email="login@example.com", password="StrongPass123!")
        response = self.client.post(
            reverse("accounts:login"),
            {"email": "login@example.com", "password": "WrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(response.data["success"])

    def test_profile_retrieve_and_update(self):
        user = User.objects.create_user(
            email="profile@example.com", password="StrongPass123!", currency="USD"
        )
        self.client.force_authenticate(user=user)
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "profile@example.com")

        update = self.client.patch(
            reverse("accounts:profile"),
            {"first_name": "Updated", "bio": "Hello", "currency": "eur"},
            format="json",
        )
        self.assertEqual(update.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Updated")
        self.assertEqual(user.currency, "eur")
        self.assertEqual(user.profile.bio, "Hello")

    def test_change_password_and_logout_blacklists_refresh_token(self):
        user = User.objects.create_user(email="pw@example.com", password="OldPass123!")
        login = self.client.post(
            reverse("accounts:login"),
            {"email": "pw@example.com", "password": "OldPass123!"},
            format="json",
        )
        refresh = login.data["data"]["refresh"]
        self.client.force_authenticate(user=user)

        changed = self.client.post(
            reverse("accounts:change-password"),
            {
                "old_password": "OldPass123!",
                "new_password": "NewPass123!",
                "new_password2": "NewPass123!",
            },
            format="json",
        )
        self.assertEqual(changed.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.check_password("NewPass123!"))

        logout = self.client.post(
            reverse("accounts:logout"), {"refresh": refresh}, format="json"
        )
        self.assertEqual(logout.status_code, status.HTTP_205_RESET_CONTENT)
        reused = self.client.post(reverse("accounts:token-refresh"), {"refresh": refresh}, format="json")
        self.assertIn(reused.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_400_BAD_REQUEST))

    def test_protected_endpoint_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
