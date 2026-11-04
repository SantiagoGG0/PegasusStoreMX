from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from catalog.models import ProductReview
from catalog.services.reviews import recalculate_product_rating


@receiver(post_save, sender=ProductReview)
def product_review_saved(sender, instance: ProductReview, **kwargs):
    recalculate_product_rating(instance.product_id)


@receiver(post_delete, sender=ProductReview)
def product_review_deleted(sender, instance: ProductReview, **kwargs):
    recalculate_product_rating(instance.product_id)
