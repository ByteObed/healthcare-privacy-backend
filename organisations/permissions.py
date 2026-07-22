from rest_framework import permissions


class IsOrganisationUser(permissions.BasePermission):
    """Allows access only to authenticated users who have a linked Organisation."""

    message = "You must be registered as an organisation to perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            hasattr(request.user, 'organisation')
        )