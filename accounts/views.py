from django.shortcuts import render


def my_account(request):
    """The logged-in user's own page.

    For now a simple placeholder; the resident portal (profile, vehicles, visitors) replaces it later.
    Login is required by LoginRequiredMiddleware, so no decorator is needed here.
    """
    return render(request, "accounts/my_account.html")
