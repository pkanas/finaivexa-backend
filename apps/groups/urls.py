from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

app_name = "groups"

router = DefaultRouter()
router.register(r"", views.GroupViewSet, basename="group")

urlpatterns = router.urls + [
    path("<int:group_pk>/members", views.GroupMembersView.as_view(), name="group-members"),
    path(
        "<int:group_pk>/members/<int:member_pk>",
        views.GroupMemberDetailView.as_view(),
        name="group-member-detail",
    ),
    path("<int:group_pk>/expenses", views.GroupExpensesView.as_view(), name="group-expenses"),
    path(
        "<int:group_pk>/expenses/<int:expense_pk>",
        views.GroupExpenseDetailView.as_view(),
        name="group-expense-detail",
    ),
    path(
        "<int:group_pk>/settlements",
        views.SettlementsView.as_view(),
        name="group-settlements",
    ),
]
