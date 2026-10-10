"""Serializers for the API.

Owner contact details are deliberately absent. Guards can see a vehicle's owner
name and flat on the HTML Vehicles page, but not phone or email, and the API
must not become a way around that restriction. Only the fields listed here are
ever returned.
"""

from rest_framework import serializers

from tracking.models import VehicleLog
from vehicles.models import Vehicle


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

    'category' is a classification, not a verdict. UNKNOWN means the plate did
    not match a registered vehicle or an expected visitor; it does not mean the
    vehicle was unauthorised.
    """

    movement_type_display = serializers.CharField(source="get_movement_type_display", read_only=True)
    category_display = serializers.CharField(source="get_category_display", read_only=True)
    owner_name = serializers.SerializerMethodField()

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
