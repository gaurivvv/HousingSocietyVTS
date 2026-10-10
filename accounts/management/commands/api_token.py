"""Issue, check and revoke API tokens for approved clients.

A token identifies a user to the API. It grants nothing on its own: the user's
group permissions still apply at every endpoint, so a token belonging to
someone without permission still receives 403.

The full token is printed ONCE, when it is issued. It is never written to a
file, never logged, and never returned by any other command or endpoint. If it
is lost, revoke it and issue a new one.

DRF's tokens do not expire. Revoke a token the moment a client no longer needs
it.
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from rest_framework.authtoken.models import Token

from accounts.roles import RESIDENT


class Command(BaseCommand):
    help = "Issue, show or revoke an API token for a user."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=["issue", "show", "revoke"])
        parser.add_argument("username")
        parser.add_argument(
            "--rotate",
            action="store_true",
            help="With 'issue': replace an existing token with a new one.",
        )

    def handle(self, *args, **options):
        action = options["action"]
        username = options["username"]

        user = User.objects.filter(username=username).first()
        if user is None:
            raise CommandError(f"No user named {username!r}.")

        if action == "issue":
            self._issue(user, rotate=options["rotate"])
        elif action == "show":
            self._show(user)
        else:
            self._revoke(user)

    def _refuse_if_unsuitable(self, user):
        """An API token should go only to an account that can actually use one."""
        if not user.is_active:
            raise CommandError(
                f"{user.username} is not active. Reactivate the account first."
            )
        if user.groups.filter(name=RESIDENT).exists():
            raise CommandError(
                f"{user.username} is in the {RESIDENT} group. Residents hold no API "
                "permissions, so a token would be refused at every endpoint. "
                "If this account is meant to be an API client, change its role first."
            )

    def _issue(self, user, rotate):
        self._refuse_if_unsuitable(user)

        existing = Token.objects.filter(user=user).first()
        if existing and not rotate:
            raise CommandError(
                f"{user.username} already has a token (starts {existing.key[:8]}...). "
                "Use --rotate to replace it, or 'revoke' to remove it. "
                "The existing key cannot be displayed again."
            )

        if existing:
            existing.delete()
            self.stdout.write(self.style.WARNING(
                f"Previous token for {user.username} revoked. It will no longer work."
            ))

        token = Token.objects.create(user=user)
        groups = ", ".join(user.groups.values_list("name", flat=True)) or "no group"

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Token issued for {user.username} ({groups})"))
        self.stdout.write("")
        self.stdout.write(f"    {token.key}")
        self.stdout.write("")
        self.stdout.write("Send it as a header on each request:")
        self.stdout.write(f"    Authorization: Token {token.key}")
        self.stdout.write("")
        self.stdout.write(self.style.WARNING(
            "This is the only time the full token is shown. Store it securely.\n"
            "Do not commit it, paste it into a chat, or include it in a screenshot.\n"
            "Over plain HTTP anyone on the network can read it: use HTTPS outside\n"
            "local development."
        ))

    def _show(self, user):
        """Report whether a token exists. Never prints the whole key."""
        token = Token.objects.filter(user=user).first()
        if token is None:
            self.stdout.write(f"{user.username} has no API token.")
            return
        groups = ", ".join(user.groups.values_list("name", flat=True)) or "no group"
        self.stdout.write(f"{user.username} ({groups}) has a token.")
        self.stdout.write(f"  starts with : {token.key[:8]}...")
        self.stdout.write(f"  created     : {token.created:%d %b %Y %H:%M}")
        self.stdout.write("  The full key is never shown again. Rotate it if it is lost.")

    def _revoke(self, user):
        deleted, _ = Token.objects.filter(user=user).delete()
        if deleted:
            self.stdout.write(self.style.SUCCESS(
                f"Token for {user.username} revoked. It no longer works."
            ))
        else:
            self.stdout.write(f"{user.username} had no API token. Nothing to revoke.")
