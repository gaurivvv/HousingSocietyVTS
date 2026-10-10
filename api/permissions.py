"""Permission classes mirroring the Django permissions used by the HTML views.

The API must not be an easier door into the same data. Each endpoint requires
the same permission its HTML equivalent requires.
"""

from rest_framework.permissions import BasePermission


class HasDjangoPermission(BasePermission):
    """Require a named Django permission, e.g. 'vehicles.view_vehicle'."""

    required_permission = None

    def has_permission(self, request, view):
        permission = getattr(view, "required_permission", self.required_permission)
        if permission is None:
            return False
        return request.user.has_perm(permission)


def requires(permission_name):
    """Build a permission class for one Django permission."""
    return type(
        "Requires_" + permission_name.replace(".", "_"),
        (HasDjangoPermission,),
        {"required_permission": permission_name},
    )
