from django.shortcuts import render

from residents.utils import get_linked_resident


def my_account(request):
    """The logged-in user's own account page (resident portal: My Account + My Vehicles).

    The resident is identified ONLY through the Resident.user link, via
    get_linked_resident(). Nothing is looked up by username, email, phone or name,
    and no resident or vehicle id is ever taken from the URL.

    States:
    - "unlinked": no resident is linked to this login (also Guards and Society Admins)
    - "inactive": the linked resident is inactive; no resident data is shown
    - "active":   the linked, active resident's own details and own vehicles are shown

    Login is required by LoginRequiredMiddleware, so no decorator is needed here.
    """
    resident = get_linked_resident(request.user)
    vehicles = None

    if resident is None:
        state = "unlinked"
    elif not resident.is_active:
        state = "inactive"
        resident = None  # never pass an inactive resident's data to the template
    else:
        state = "active"
        # Only this resident's own vehicles, through Vehicle.resident (related_name="vehicles")
        vehicles = resident.vehicles.order_by("vehicle_number")

    context = {"portal_state": state, "resident": resident, "vehicles": vehicles}
    return render(request, "accounts/my_account.html", context)
