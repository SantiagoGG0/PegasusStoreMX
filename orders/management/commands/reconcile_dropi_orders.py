"""Pone al día los pedidos de la tienda con la lista completa de Dropi
(ver orders/reconcile.py). Seguro de repetir; pensado para correr programado.

    python manage.py reconcile_dropi_orders --dry-run          # solo muestra
    python manage.py reconcile_dropi_orders --notify-days 0    # primera vez: sin avisos
    python manage.py reconcile_dropi_orders                    # avisa cambios de pedidos de los últimos 3 días
"""
from django.core.management.base import BaseCommand

from dropi_client.client import DropiClient
from orders.reconcile import reconcile


class Command(BaseCommand):
    help = "Cruza los pedidos de la tienda con las órdenes de Dropi y actualiza estados, guías y transportadoras."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="No guarda nada; muestra el emparejamiento.")
        parser.add_argument(
            "--notify-days", type=int, default=3,
            help="Avisar al cliente solo si el pedido tiene a lo sumo estos días (0 = no avisar a nadie).",
        )

    def handle(self, *args, **opts):
        stats = reconcile(DropiClient(), dry_run=opts["dry_run"], notify_days=opts["notify_days"])
        for row in stats["rows"]:
            self.stdout.write("  pedido #%s: %s → Dropi %s %s%s" % (
                row[0], row[1], row[2], row[3], f" → ahora {row[4]}" if len(row) > 4 else ""))
        self.stdout.write(
            f"Órdenes en Dropi: {stats['dropi_orders']} · pedidos emparejados: {stats['matched']} · "
            f"actualizados: {stats['changed']} · reactivados: {stats['revived']} · avisos: {stats['notified']}"
        )
        if opts["dry_run"]:
            self.stdout.write("Simulación: no se cambió nada.")
        else:
            self.stdout.write(self.style.SUCCESS("OK"))
