"""Serializers for the API.

Owner contact details are restricted appropriately:
- General endpoints (vehicles, gate logs) expose only the minimum context.
- The resident portal endpoints expose the authenticated resident's own vehicles and visitors.
"""

from rest_framework import serializers

from tracking.models import VehicleLog
from vehicles.models import Vehicle
from visitors.models import Visitor
from residents.models import Resident


class VehicleSerializer(serializers.ModelSerializer):
    """A registered vehicle, with the minimum owner context needed to act on it."""

    vehicle_type_display = serializers.CharField(source="get_vehicle_type_display", read_only=True)
    owner_name = serializers.CharField(source="resident.full_name", read_only=True)
    owner_flat = serializers.CharField(source="resident.flat.__str__", read_only=True)

    class Meta:
        model = Vehicle
        fields = [
            "id",
            "vehicle_number",
            "vehicle_type",
            "vehicle_type_display",
            "model_name",
            "colour",
            "is_active",
            "owner_name",
            "owner_flat",
        ]
        read_only_fields = fields


class VehicleLogSerializer(serializers.ModelSerializer):
    """A gate movement.

    The owner or visitor name is included so a guard can see who a movement
    relates to, but no contact details are exposed, consistent with the
    vehicle endpoints and with the HTML Gate History page.
    """

    movement_type_display = serializers.CharField(source="get_movement_type_display", read_only=True)
    category_display = serializers.CharField(source="get_category_display", read_only=True)
    owner_name = serializers.SerializerMethodField()
    recorded_by = serializers.CharField(
        source="recorded_by.username", read_only=True, default=None
    )

    class Meta:
        model = VehicleLog
        fields = [
            "id",
            "timestamp",
            "plate_number",
            "movement_type",
            "movement_type_display",
            "category",
            "category_display",
            "owner_name",
            "recorded_by",
            "remarks",
        ]
        read_only_fields = fields

    def get_owner_name(self, log):
        """Resident name for a registered vehicle, visitor name for a visitor."""
        if log.vehicle_id and log.vehicle.resident_id:
            return log.vehicle.resident.full_name
        if log.visitor_id:
            return log.visitor.full_name
        return None


class VisitorSerializer(serializers.ModelSerializer):
    """A visitor record, including status, pass code, and visit timestamps."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    flat_name = serializers.CharField(source="flat.__str__", read_only=True)
    resident_name = serializers.CharField(source="resident.full_name", read_only=True)

    class Meta:
        model = Visitor
        fields = [
            "id",
            "full_name",
            "phone",
            "vehicle_number",
            "flat_name",
            "resident_name",
            "expected_date",
            "entry_time",
            "exit_time",
            "status",
            "status_display",
            "pass_code",
            "created_at",
        ]
        read_only_fields = ["id", "pass_code", "status", "entry_time", "exit_time", "created_at"]


class ResidentPortalSerializer(serializers.ModelSerializer):
    """The authenticated resident's self-service profile with vehicles and visitors."""

    flat_name = serializers.CharField(source="flat.__str__", read_only=True)
    wing_name = serializers.CharField(source="flat.wing.name", read_only=True)
    resident_type_display = serializers.CharField(source="get_resident_type_display", read_only=True)
    vehicles = VehicleSerializer(many=True, read_only=True)
    visitors = VisitorSerializer(many=True, read_only=True)

    class Meta:
        model = Resident
        fields = [
            "id",
            "full_name",
            "resident_type",
            "resident_type_display",
            "phone",
            "email",
            "flat_name",
            "wing_name",
            "vehicles",
            "visitors",
        ]
        read_only_fields = fields
