from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

from apps.categories.models import Category
from apps.common.testing import BaseAPITestCase

User = get_user_model()


class CategoryTests(BaseAPITestCase):
    def test_default_categories_created_for_new_user(self):
        self.assertGreaterEqual(
            Category.objects.filter(user=None, type=Category.Type.EXPENSE).count(), 10
        )
        self.assertGreaterEqual(
            Category.objects.filter(user=None, type=Category.Type.INCOME).count(), 5
        )

    def test_list_returns_defaults_and_custom(self):
        Category.objects.create(
            user=self.user, name="Pets", type=Category.Type.EXPENSE, icon="paw"
        )
        response = self.client.get(reverse("categories:category-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [item["name"] for item in response.data["data"]["results"]]
        self.assertIn("Pets", names)
        self.assertIn("Food & Dining", names)

    def test_filter_by_type_and_search(self):
        response = self.client.get(reverse("categories:category-list"), {"type": "income"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["data"]["results"]
        self.assertTrue(results)
        self.assertTrue(all(item["type"] == "income" for item in results))

    def test_create_custom_category_and_reject_duplicate(self):
        payload = {"name": "Pets", "type": "expense", "icon": "paw", "color": "#fff"}
        created = self.client.post(reverse("categories:category-list"), payload, format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        category = Category.objects.get(name="Pets", user=self.user)
        self.assertFalse(category.is_default)

        duplicate = self.client.post(reverse("categories:category-list"), payload, format="json")
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_delete_default_category(self):
        default = self.category()
        response = self.client.delete(
            reverse("categories:category-detail", args=[default.pk])
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Category.objects.filter(pk=default.pk).exists())

    def test_cannot_access_another_users_custom_category(self):
        other = User.objects.create_user(email="other@example.com", password="StrongPass123!")
        private = Category.objects.create(
            user=other, name="Secret", type=Category.Type.EXPENSE
        )
        response = self.client.get(
            reverse("categories:category-detail", args=[private.pk])
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
