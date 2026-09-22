"""
Roles of the Housing Society system.

This is the single place where each role's permissions are listed.
`python manage.py setup_roles` makes the database groups match these lists exactly.

Note: Django Admin access is controlled separately by each user's `is_staff` flag
(Society Admins: True; Guards and Residents: False).
"""

SOCIETY_ADMIN = "Society Admin"
GUARD = "Guard"
RESIDENT = "Resident"

# Permissions are written as (app_label, codename).
# No role has any "delete_" permission: historical records are never deleted;
# people and vehicles are deactivated instead.

SOCIETY_ADMIN_PERMISSIONS = [
    ("society", "add_wing"), ("society", "change_wing"), ("society", "view_wing"),
    ("society", "add_flat"), ("society", "change_flat"), ("society", "view_flat"),
    ("residents", "add_resident"), ("residents", "change_resident"), ("residents", "view_resident"),
    ("vehicles", "add_vehicle"), ("vehicles", "change_vehicle"), ("vehicles", "view_vehicle"),
    ("visitors", "add_visitor"), ("visitors", "change_visitor"), ("visitors", "view_visitor"),
    ("visitors", "check_in_out_visitor"), ("visitors", "cancel_visitor"),
    ("tracking", "add_vehiclelog"), ("tracking", "change_vehiclelog"), ("tracking", "view_vehiclelog"),
    ("auth", "add_user"), ("auth", "change_user"), ("auth", "view_user"),
    ("auth", "view_group"),
]

GUARD_PERMISSIONS = [
    ("tracking", "add_vehiclelog"), ("tracking", "view_vehiclelog"),
    ("visitors", "add_visitor"), ("visitors", "view_visitor"),
    ("visitors", "check_in_out_visitor"), ("visitors", "cancel_visitor"),
    ("vehicles", "view_vehicle"),
]

# Residents get no model permissions: they only see their own data,
# through the link between their login and their Resident record.
RESIDENT_PERMISSIONS = []

ROLE_PERMISSIONS = {
    SOCIETY_ADMIN: SOCIETY_ADMIN_PERMISSIONS,
    GUARD: GUARD_PERMISSIONS,
    RESIDENT: RESIDENT_PERMISSIONS,
}
