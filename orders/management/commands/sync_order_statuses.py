"""
Management command: sync_order_statuses

Polls the Dropi API for each active order and updates local status,
shipping guide, and carrier when they change. Sends email notifications
to customers on status transitions.

Usage:
    python manage.py sync_order_statuses
    python manage.py sync_order_statuses --order-id 75482548
    python manage.py sync_order_statuses --dry-run

Schedule:
    Add to cron (every 15 minutes recommended):
        */15 * * * * /path/to/venv/bin/python /path/to/manage.py sync_order_statuses >> /var/log/dropi_sync.log 2>&1

    Or use Django management via APScheduler / Celery Beat if available.
"""

import logging
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from dropi_client.client import DropiClient
from dropi_client.exceptions import DropiAPIError
from orders.models import Order
from orders.services import (
    notify_status_change,
    send_whatsapp_notification,
    sync_order_from_dropi,
)

logger = logging.getLogger(__name__)

# Statuses that are still "in flight" and worth polling
_ACTIVE_STATUSES = [
    Order.STATUS_PENDING,
    Order.STATUS_CONFIRMED,
    Order.STATUS_SENT,
]


class Command(BaseCommand):
    help = "Sync order statuses from Dropi API and notify customers on changes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--order-id",
            dest="dropi_order_id",
            default=None,
            help="Only sync a specific Dropi order ID.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Fetch and print status without saving or sending notifications.",
        )
        parser.add_argument(
            "--no-notify",
            action="store_true",
            default=False,
            help="Update local status but skip sending notification emails.",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            default=False,
            help="Sync all orders with Dropi ID (not only active statuses).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limit number of orders to sync (useful for batches).",
        )
        parser.add_argument(
            "--watch",
            action="store_true",
            default=False,
            help="Run continuously and sync in a loop.",
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=5,
            help="Seconds between sync cycles when using --watch (default: 5).",
        )
        parser.add_argument(
            "--max-cycles",
            type=int,
            default=None,
            help="Stop after N cycles in --watch mode (useful for testing).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        no_notify = options["no_notify"]
        filter_id = options["dropi_order_id"]
        include_all = options["all"]
        limit = options["limit"]
        watch = options["watch"]
        interval = max(1, int(options["interval"]))
        max_cycles = options["max_cycles"]

        client = DropiClient()

        cycle = 0
        while True:
            cycle += 1

            qs = Order.objects.filter(dropi_order_id__gt="")
            if not include_all:
                qs = qs.filter(status__in=_ACTIVE_STATUSES)
            if filter_id:
                qs = qs.filter(dropi_order_id=filter_id)
            qs = qs.order_by("last_dropi_sync", "-created_at")
            if limit:
                qs = qs[:limit]

            total = qs.count()
            prefix = f"[sync_order_statuses][cycle {cycle}] " if watch else "[sync_order_statuses] "
            self.stdout.write(
                f"{prefix}{'DRY RUN — ' if dry_run else ''}"
                f"Checking {total} order(s) "
                f"({'all statuses' if include_all else 'active statuses only'})…"
            )

            if total == 0:
                self.stdout.write("  Nothing to do.")
                if not watch:
                    return
            updated = 0
            unchanged = 0
            failed = 0

            for order in qs.iterator():
                try:
                    data = client.get_order(order.dropi_order_id)

                    if dry_run:
                        from orders.services import (
                            _map_dropi_status,
                            _extract_objects,
                            build_tracking_url,
                        )
                        obj = _extract_objects(data)
                        raw = str(obj.get("status") or obj.get("estado") or "").strip()
                        mapped = _map_dropi_status(raw) or "?"
                        guide = (
                            obj.get("shipping_guide") or obj.get("guide_number") or obj.get("guide")
                            or obj.get("numeral_guide") or obj.get("guia")
                            or obj.get("numero_guia") or obj.get("tracking") or ""
                        )
                        carrier = obj.get("shipping_company") or obj.get("carrier") or ""
                        tracking = build_tracking_url(carrier, guide) if guide and carrier else ""
                        self.stdout.write(
                            f"  #{order.pk} (Dropi {order.dropi_order_id}): "
                            f"local={order.status} → dropi={raw} (maps to {mapped}) "
                            f"guide={guide} carrier={carrier}"
                        )
                        if tracking:
                            self.stdout.write(f"    tracking_url: {tracking}")
                        if options.get("verbosity", 1) >= 2:
                            self.stdout.write(f"    Response keys: {list(obj.keys())}")
                        continue

                    changed, old_status = sync_order_from_dropi(order, data)

                    if changed:
                        updated += 1
                        status_changed = order.status != old_status
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  #{order.pk}: {old_status} → {order.status}"
                                + (f" | guía: {order.shipping_guide}" if order.shipping_guide else "")
                                + (f" ({order.carrier})" if order.carrier else "")
                                + (f" | url: {order.tracking_url}" if order.tracking_url else "")
                            )
                        )
                        if not no_notify and status_changed:
                            sent_mail = notify_status_change(order, old_status)
                            sent_wa = send_whatsapp_notification(order, old_status)
                            if sent_mail:
                                self.stdout.write(f"    ✉ Email enviado a {order.email}")
                            if sent_wa:
                                self.stdout.write(f"    WhatsApp enviado a {order.phone}")
                    else:
                        unchanged += 1

                except DropiAPIError as exc:
                    failed += 1
                    logger.warning("Dropi API error for order #%s (Dropi %s): %s", order.pk, order.dropi_order_id, exc)
                    self.stdout.write(
                        self.style.WARNING(f"  #{order.pk} SKIPPED — {exc}")
                    )
                except Exception as exc:
                    failed += 1
                    logger.exception("Unexpected error syncing order #%s: %s", order.pk, exc)
                    self.stdout.write(
                        self.style.ERROR(f"  #{order.pk} ERROR — {exc}")
                    )

            if not dry_run:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\nDone at {timezone.now():%Y-%m-%d %H:%M:%S} — "
                        f"{updated} updated, {unchanged} unchanged, {failed} failed."
                    )
                )

            if not watch:
                return
            if max_cycles and cycle >= max_cycles:
                self.stdout.write("Reached --max-cycles, exiting.")
                return
            self.stdout.write(f"Waiting {interval}s for next cycle... (Ctrl+C to stop)")
            try:
                time.sleep(interval)
            except KeyboardInterrupt:
                self.stdout.write("Stopped by user.")
                return
