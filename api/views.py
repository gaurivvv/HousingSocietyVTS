from datetime import timedelta

from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from residents.models import Resident
from residents.utils import get_linked_resident
from society.models import Flat, Wing
from tracking.anpr_service import run_anpr
from tracking.models import VehicleLog
from tracking.utils import todays_counts, vehicles_inside
from vehicles.models import Vehicle
from vehicles.utils import normalize_plate
from visitors.models import Visitor

from .permissions import requires
from .serializers import (
    ResidentPortalSerializer,
    VehicleLogSerializer,
    VehicleSerializer,
    VisitorSerializer,
)

CanViewVehicle = requires("vehicles.view_vehicle")
CanViewVehicleLog = requires("tracking.view_vehiclelog")
CanAddVehicleLog = requires("tracking.add_vehiclelog")
CanViewVisitor = requires("visitors.view_visitor")
CanCheckInOutVisitor = requires("visitors.check_in_out_visitor")

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


@api_view(["POST"])
@permission_classes([CanAddVehicleLog])
@parser_classes([MultiPartParser, FormParser])
def gate_anpr_scan(request):
    """Scan an image using the ANPR pipeline to suggest a candidate plate.

    This produces an unverified candidate observation for operator review.
    It does NOT record a VehicleLog entry.
    """
    if "image" not in request.FILES:
        return Response(
            {"error": "image_required", "detail": "An 'image' file upload is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    image_file = request.FILES["image"]
    anpr_data = run_anpr(image_file)

    if not anpr_data.get("success"):
        return Response(
            {
                "success": False,
                "error": "anpr_detection_failed",
                "detail": anpr_data.get("error", "Vehicle or plate could not be resolved."),
            },
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    candidate = (anpr_data.get("candidate_plate") or "").strip()
    return Response(
        {
            "success": True,
            "candidate_plate": candidate,
            "raw_text": anpr_data.get("raw_text", ""),
            "vehicle_detected": anpr_data.get("vehicle_detected", False),
            "vehicle_type": anpr_data.get("vehicle_type"),
            "vehicle_confidence": anpr_data.get("vehicle_confidence"),
            "plate_detected": anpr_data.get("plate_detected", False),
            "plate_confidence": anpr_data.get("plate_confidence"),
            "ocr_confidence": anpr_data.get("ocr_confidence"),
            "format_status": anpr_data.get("format_status"),
            "corrections": anpr_data.get("corrections", []),
            "uncertain": anpr_data.get("uncertain", False),
            "recorded": False,
            "instruction": (
                "This candidate plate has NOT been saved to the gate log. "
                "The operator must verify the plate with the driver, then submit "
                "the confirmed movement to /api/v1/gate/anpr-log/ with source='manual'."
            ),
        },
        status=status.HTTP_200_OK,
    )


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


# ----- Mobile App Endpoints -----

@api_view(["POST"])
@permission_classes([AllowAny])
def auth_login(request):
    """Mobile login returning authentication token, role, and resident profile."""
    username = str(request.data.get("username", "")).strip()
    password = str(request.data.get("password", ""))

    if not username or not password:
        return Response(
            {"error": "credentials_required", "detail": "Username and password are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response(
            {"error": "invalid_credentials", "detail": "Invalid username or password."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    token, _ = Token.objects.get_or_create(user=user)

    if user.is_staff or user.groups.filter(name="Society Admin").exists():
        role = "Society Admin"
    elif user.groups.filter(name="Guard").exists():
        role = "Guard"
    elif user.groups.filter(name="Resident").exists() or hasattr(user, "resident"):
        role = "Resident"
    else:
        role = "User"

    linked_resident = get_linked_resident(user)
    resident_data = ResidentPortalSerializer(linked_resident).data if linked_resident else None

    return Response({
        "token": token.key,
        "user_id": user.pk,
        "username": user.get_username(),
        "role": role,
        "is_staff": user.is_staff,
        "resident": resident_data,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def resident_me(request):
    """Retrieve the authenticated resident's profile, vehicles, and visitors."""
    resident = get_linked_resident(request.user)
    if resident is None:
        return Response(
            {"error": "no_linked_resident", "detail": "No resident record is linked to this account."},
            status=status.HTTP_404_NOT_FOUND,
        )
    if not resident.is_active:
        return Response(
            {"error": "inactive_resident", "detail": "This resident account is inactive."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return Response(ResidentPortalSerializer(resident).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def resident_create_visitor(request):
    """Pre-register a visitor from the resident mobile app."""
    resident = get_linked_resident(request.user)
    if resident is None or not resident.is_active:
        return Response(
            {"error": "forbidden", "detail": "Only active linked residents can pre-register visitors."},
            status=status.HTTP_403_FORBIDDEN,
        )

    full_name = str(request.data.get("full_name", "")).strip()
    phone = str(request.data.get("phone", "")).strip()
    vehicle_number = str(request.data.get("vehicle_number", "")).strip()
    expected_date = request.data.get("expected_date") or timezone.localdate()

    if not full_name or not phone:
        return Response(
            {"error": "missing_fields", "detail": "Full name and phone are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        visitor = Visitor(
            full_name=full_name,
            phone=phone,
            vehicle_number=vehicle_number,
            flat=resident.flat,
            resident=resident,
            expected_date=expected_date,
        )
        visitor.full_clean()
        visitor.save()
        return Response(VisitorSerializer(visitor).data, status=status.HTTP_201_CREATED)
    except ValidationError as err:
        return Response(
            {"error": "validation_error", "detail": err.message_dict if hasattr(err, "message_dict") else str(err)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
@permission_classes([CanViewVisitor])
def visitor_list_guard(request):
    """List expected and checked-in visitors for gate management."""
    date_str = request.query_params.get("date")
    if date_str:
        try:
            target_date = timezone.datetime.fromisoformat(date_str).date()
        except ValueError:
            target_date = timezone.localdate()
    else:
        target_date = timezone.localdate()

    visitors = Visitor.objects.filter(expected_date=target_date).select_related("flat__wing", "resident")

    status_filter = request.query_params.get("status")
    if status_filter:
        visitors = visitors.filter(status=status_filter.upper())

    q = request.query_params.get("q", "").strip()
    if q:
        norm = normalize_plate(q)
        q_cond = (
            Q(full_name__icontains=q)
            | Q(phone__icontains=q)
            | Q(pass_code__icontains=q)
        )
        if norm:
            q_cond |= Q(vehicle_number__icontains=norm)
        visitors = visitors.filter(q_cond)

    serializer = VisitorSerializer(visitors, many=True)
    return Response({"count": visitors.count(), "results": serializer.data})


@api_view(["POST"])
@permission_classes([CanCheckInOutVisitor])
def visitor_check_in(request, pk):
    """Check in an expected visitor by ID."""
    visitor = get_object_or_404(Visitor, pk=pk)
    try:
        visitor.check_in()
        return Response(VisitorSerializer(visitor).data)
    except ValidationError as err:
        return Response({"error": "action_failed", "detail": str(err)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([CanCheckInOutVisitor])
def visitor_check_out(request, pk):
    """Check out a checked-in visitor by ID."""
    visitor = get_object_or_404(Visitor, pk=pk)
    try:
        visitor.check_out()
        return Response(VisitorSerializer(visitor).data)
    except ValidationError as err:
        return Response({"error": "action_failed", "detail": str(err)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    """Real-time society statistics for mobile dashboard overview."""
    user = request.user
    if not (user.has_perm("tracking.view_vehiclelog") or user.has_perm("residents.view_resident")):
        return Response(
            {"error": "forbidden", "detail": "You do not have permission to view society metrics."},
            status=status.HTTP_403_FORBIDDEN,
        )

    today = todays_counts()
    return Response({
        "wing_count": Wing.objects.count(),
        "flat_count": Flat.objects.count(),
        "active_resident_count": Resident.objects.filter(is_active=True).count(),
        "active_vehicle_count": Vehicle.objects.filter(is_active=True).count(),
        "inside_count": vehicles_inside().count(),
        "todays_entries": today["entries"],
        "todays_exits": today["exits"],
        "todays_visitor_count": Visitor.objects.filter(expected_date=timezone.localdate()).count(),
    })
