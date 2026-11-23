"""Object-level permissions for user-owned and group-owned resources."""
from rest_framework import permissions


class IsOwner(permissions.BasePermission):
    """Only the owning user may access an object."""

    def has_object_permission(self, request, view, obj):
        owner = getattr(obj, "user", None)
        return owner is not None and owner.pk == request.user.pk


class IsGroupMember(permissions.BasePermission):
    """Only members of the related group may access an object."""

    def has_object_permission(self, request, view, obj):
        group = obj if hasattr(obj, "memberships") else getattr(obj, "group", None)
        if group is None:
            return False
        return group.members.filter(pk=request.user.pk).exists()


class IsGroupAdmin(permissions.BasePermission):
    """Only admins of the related group may modify it."""

    def has_object_permission(self, request, view, obj):
        group = obj if hasattr(obj, "memberships") else getattr(obj, "group", None)
        if group is None:
            return False
        return group.memberships.filter(
            user=request.user, role="admin"
        ).exists()
