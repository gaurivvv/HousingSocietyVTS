"""API views.

Every endpoint applies the same Django permission as its HTML equivalent, so
the API cannot be used to reach data a role could not reach in the browser.
"""

from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from tracking.models import VehicleLog
from vehicles.models import Vehicle
from vehicles.utils import normalize_plate

from .permissions import requires
from .serializers import VehicleLogSerializer, VehicleSerializer

CanViewVehicle = requires("vehicles.view_vehicle")
CanViewVehicleLog = requires("tracking.view_vehiclelog")
CanAddVehicleLog = requires("tracking.add_vehiclelog")


@api_view(["GET"])
def ping(request):
    """Confirm the API is reachable and report who is calling.

    Requires an authenticated session. Exposes nothing beyond the caller's own
    username and group names, which the caller already knows about themselves.
    """
    return Response({
        "status": "ok",
        "api_version": "v1",
        "user": request.user.get_username(),
        "groups": sorted(request.user.groups.values_list("name", flat=True)),
    })


@api_view(["GET"])
@permission_classes([CanViewVehicle])
def vehicle_list(request):
    """List registered vehicles, newest registration first.

    Optional query parameters:
        active=true|false   filter by is_active
        type=<code>         filter by vehicle_type
    """
    vehicles = Vehicle.objects.select_related("resident", "resident__flat", "resident__flat__wing")

    active = request.query_params.get("active")
    if active is not None:
        if active.lower() in ("true", "1"):
            vehicles = vehicles.filter(is_active=True)
        elif active.lower() in ("false", "0"):
            vehicles = vehicles.filter(is_active=False)

    vehicle_type = request.query_params.get("type")
    if vehicle_type:
        vehicles = vehicles.filter(vehicle_type=vehicle_type.upper())

    vehicles = vehicles.order_by("vehicle_number")
    serializer = VehicleSerializer(vehicles, many=True)
    return Response({"count": vehicles.count(), "results": serializer.data})


@api_view(["GET"])
@permission_classes([CanViewVehicle])
def vehicle_lookup(request):
    """Look up one registered vehicle by plate number.

    The plate is normalized with the project's existing normalize_plate(), so
    'mh 12 kl 4567' and 'MH12KL4567' reach the same record.

    A 404 means the plate is not registered. It does NOT mean the vehicle is
    unauthorized; visitors and other legitimate vehicles are simply not in the
    Vehicle table.
    """
    raw_plate = request.query_params.get("plate", "")
    if not raw_plate.strip():
        return Response(
            {"detail": "A 'plate' query parameter is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    normalized = normalize_plate(raw_plate)
    if not normalized:
        return Response(
            {"detail": "The plate could not be normalized to a usable value.",
             "submitted": raw_plate},
            status=status.HTTP_400_BAD_REQUEST,
        )

    vehicle = (
        Vehicle.objects
        .select_related("resident", "resident__flat", "resident__flat__wing")
        .filter(vehicle_number=normalized)
        .first()
    )

    if vehicle is None:
        return Response(
            {"detail": "No registered vehicle matches this plate.",
             "submitted": raw_plate,
             "normalized": normalized,
             "registered": False},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response({
        "submitted": raw_plate,
        "normalized": normalized,
        "registered": True,
        "vehicle": VehicleSerializer(vehicle).data,
    })

@api_view(["GET"])
@permission_classes([CanViewVehicleLog])
def gate_log_list(request):
    """List recent gate movements, newest first.

    Optional query parameters:
        plate=<text>        filter by normalized plate
        movement=ENTRY|EXIT filter by direction
        category=<code>     filter by classification
        limit=<n>           cap the number returned (default 50, max 200)
    """
    logs = VehicleLog.objects.select_related(
        "vehicle", "vehicle__resident", "visitor"
    ).order_by("-timestamp")

    plate = request.query_params.get("plate")
    if plate:
        normalized = normalize_plate(plate)
        if normalized:
            logs = logs.filter(plate_number__icontains=normalized)

    movement = request.query_params.get("movement")
    if movement:
        logs = logs.filter(movement_type=movement.upper())

    category = request.query_params.get("category")
    if category:
        logs = logs.filter(category=category.upper())

    try:
        limit = int(request.query_params.get("limit", 50))
    except (TypeError, ValueError):
        limit = 50
    limit = max(1, min(limit, 200))

    total = logs.count()
    logs = logs[:limit]

    return Response({
        "count": total,
        "returned": len(logs),
        "results": VehicleLogSerializer(logs, many=True).data,
    })

# A movement repeated within this window is treated as the same event, not a
# second one. Cameras and impatient fingers both produce duplicates.
DUPLICATE_WINDOW_SECONDS = 60

# Fields a client might send that are deliberately ignored. Identity,
# confidence and classification are never taken on a client's word.
IGNORED_FIELDS = ["ocr_confidence", "confidence", "confirmed_by_guard",
                  "resident_id", "resident", "vehicle_id", "vehicle",
                  "visitor_id", "visitor", "category", "timestamp",
                  "recorded_by", "recorded_by_id", "user", "user_id"]


@api_view(["POST"])
@permission_classes([CanAddVehicleLog])
def gate_movement(request):
    """Record a gate movement that a person has confirmed.

    Expected body:
        {"plate_number": "MH12KL4567",
         "movement_type": "ENTRY",
         "source": "manual",
         "remarks": "optional"}

    source="manual" means a guard or administrator read the plate and confirmed
    it. The movement is recorded.

    source="anpr" is REJECTED with 422. The VehicleLog model has no field that
    distinguishes an unverified camera observation from a confirmed movement,
    so storing one would misrepresent it. The guard must confirm the reading
    first and resubmit it as manual.

    The caller cannot set the category, the owner, or any confidence value.
    The plate is normalized with the project's normalize_plate(), and
    VehicleLog._apply_rules() performs the classification, exactly as the
    HTML gate form does.
    """
    data = request.data if isinstance(request.data, dict) else {}

    # 1. Source. Checked first: an ANPR submission is refused outright.
    source = str(data.get("source", "")).strip().lower()
    if source == "anpr":
        return Response(
            {
                "error": "unverified_observation_not_storable",
                "detail": (
                    "This endpoint cannot store an unverified ANPR observation. "
                    "The gate log has no field separating an automatic reading "
                    "from a movement a person confirmed, so recording it would "
                    "present an unverified reading as a confirmed fact."
                ),
                "required_action": (
                    "Show the reading to the guard. Once they confirm or correct "
                    "the plate, resubmit it with source='manual'."
                ),
                "accepted_sources": ["manual"],
            },
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    if source != "manual":
        return Response(
            {"error": "invalid_source",
             "detail": "The 'source' field must be 'manual'.",
             "accepted_sources": ["manual"]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # 2. Plate.
    raw_plate = str(data.get("plate_number", "") or "")
    if not raw_plate.strip():
        return Response(
            {"error": "plate_required",
             "detail": "A non-empty 'plate_number' is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    normalized = normalize_plate(raw_plate)
    if not normalized:
        return Response(
            {"error": "plate_not_usable",
             "detail": "The plate could not be normalized to a usable value.",
             "submitted": raw_plate},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # 3. Direction, against the model's own choices.
    movement = str(data.get("movement_type", "") or "").strip().upper()
    valid_movements = [choice for choice, _ in VehicleLog.MovementType.choices]
    if movement not in valid_movements:
        return Response(
            {"error": "invalid_movement_type",
             "detail": "The 'movement_type' field must be one of the values listed.",
             "accepted": valid_movements,
             "submitted": data.get("movement_type")},
            status=status.HTTP_400_BAD_REQUEST,
        )

    remarks = str(data.get("remarks", "") or "").strip()

    # 4. Duplicate within the window: return the existing log, create nothing.
    cutoff = timezone.now() - timedelta(seconds=DUPLICATE_WINDOW_SECONDS)
    existing = (
        VehicleLog.objects
        .select_related("vehicle", "vehicle__resident", "visitor")
        .filter(plate_number=normalized, movement_type=movement, timestamp__gte=cutoff)
        .order_by("-timestamp")
        .first()
    )
    if existing is not None:
        return Response(
            {"created": False,
             "duplicate_of_recent_movement": True,
             "detail": (
                 f"An identical movement was recorded within the last "
                 f"{DUPLICATE_WINDOW_SECONDS} seconds. No new log was created."
             ),
             "log": VehicleLogSerializer(existing).data},
            status=status.HTTP_200_OK,
        )

    # 5. Create. The model classifies; the API does not.
    # recorded_by comes from the authenticated session only. A recorded_by or
    # user field in the request body is ignored, so a caller cannot attribute
    # a movement to someone else.
    log = VehicleLog(
        plate_number=normalized,
        movement_type=movement,
        category=VehicleLog.Category.UNKNOWN,
        remarks=remarks,
        recorded_by=request.user,
    )
    log.full_clean()
    log.save()
    log.refresh_from_db()

    ignored = [field for field in IGNORED_FIELDS if field in data]

    return Response(
        {"created": True,
         "submitted": raw_plate,
         "normalized": normalized,
         "detail": (
             "Movement recorded. The category was determined by the system from "
             "the registered vehicles and today's expected visitors. A category "
             "of UNKNOWN means the plate was not recognised; it is not a "
             "judgement that the vehicle was unauthorised."
         ),
         "ignored_fields": ignored,
         "log": VehicleLogSerializer(log).data},
        status=status.HTTP_201_CREATED,
    )
