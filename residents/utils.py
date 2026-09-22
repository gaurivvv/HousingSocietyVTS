from .models import Resident


def get_linked_resident(user):
    """Return the Resident linked to this Django User, or None.

    Uses only the Resident.user relationship: nothing is guessed from a
    username, email, phone or name, and nothing is created.

    Returns None for anonymous users (or None) and for users with no linked
    Resident. No business rules are applied here; for example, an inactive
    Resident is still returned. Deciding what to show is the caller's job.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    try:
        return user.resident
    except Resident.DoesNotExist:
        # Django raises RelatedObjectDoesNotExist (a subclass of
        # Resident.DoesNotExist) when this user has no linked Resident.
        return None
