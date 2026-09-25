from django.shortcuts import render

from residents.utils import get_linked_resident


def my_account(request):
    """The logged-in user's own account page (resident portal: My Account, My Vehicles, My Visitors).

    The resident is identified ONLY through the Resident.user link, via
    get_linked_resident(). Nothing is looked up by username, email, phone, name or flat,
    and no resident, vehicle or visitor id is ever taken from the URL.

    States:
    - "unlinked": no resident is linked to this login (also Guards and Society Admins)
    - "inactive": the linked resident is inactive; no resident data is shown
    - "active":   the linked, active resident's own details, vehicles and visitors are shown

    Login is required by LoginRequiredMiddleware, so no decorator is needed here.
    """
    resident = get_linked_resident(request.user)
    vehicles = None
    visitors = None

    if resident is None:
        state = "unlinked"
    elif not resident.is_active:
        state = "inactive"
        resident = None  # never pass an inactive resident's data to the template
    else:
        state = "active"
        # Only this resident's own vehicles, through Vehicle.resident (related_name="vehicles")
        vehicles = resident.vehicles.order_by("vehicle_number")
        # Only this resident's own visitors, through Visitor.resident (related_name="visitors").
        # Never Visitor.flat: a flat can hold several residents, whose visitors are not this
        # resident's to see.
        visitors = resident.visitors.order_by("-expected_date", "-created_at")

    context = {
        "portal_state": state,
        "resident": resident,
        "vehicles": vehicles,
        "visitors": visitors,
    }
    return render(request, "accounts/my_account.html", context)
