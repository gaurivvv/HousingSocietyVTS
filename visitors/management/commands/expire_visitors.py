from django.core.management.base import BaseCommand
from django.utils import timezone

from visitors.models import Visitor


class Command(BaseCommand):
    help = "Mark expected visitors whose expected date has passed as expired."

    def handle(self, *args, **options):
        # Today's date in the project's time zone (Asia/Kolkata)
        today = timezone.localdate()

        # Only EXPECTED visitors from earlier dates; today's visitors are not touched
        overdue = Visitor.objects.filter(
            status=Visitor.Status.EXPECTED,
            expected_date__lt=today,
        )

        # One UPDATE statement; update() does not set auto_now fields, so set updated_at here
        count = overdue.update(status=Visitor.Status.EXPIRED, updated_at=timezone.now())

        date_text = today.strftime("%d %b %Y")
        if count == 0:
            self.stdout.write(f"No visitors to expire (no expected visits before {date_text}).")
        else:
            word = "visitor" if count == 1 else "visitors"
            self.stdout.write(self.style.SUCCESS(f"Expired {count} {word} expected before {date_text}."))
