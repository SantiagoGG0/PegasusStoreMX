import os
import django
from django.test import Client
from django.urls import reverse
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from catalog.models import Product

def run():
    client = Client(HTTP_HOST='localhost')
    product = Product.objects.filter(is_active=True).first()
    if not product:
        print("No active product found")
        return

    print(f"Testing with Product: {product.name} (ID: {product.id})")

    # 3) POST /carrito/agregar/<id>/ quantity=2
    # Use AJAX to get JSON response
    add_url = reverse('cart:add', kwargs={'product_id': product.id})
    response = client.post(add_url, {'quantity': 2, 'override': False}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    print(f"Add product status: {response.status_code}")
    if response.status_code == 200:
        print(f"Add Response JSON: {response.content.decode()}")

    # Check session for cart_key
    cart_session = client.session.get('cart', {})
    cart_keys = list(cart_session.keys())
    print(f"Cart keys in session: {cart_keys}")
    
    if not cart_keys:
        print("Cart is empty in session")
        return
        
    cart_key = cart_keys[0]
    
    # 4) POST /carrito/actualizar/ with cart_key and action=decrement twice
    update_url = reverse('cart:update')
    
    for i in range(2):
        response = client.post(update_url, 
                               {'cart_key': cart_key, 'action': 'decrement'}, 
                               HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        print(f"Update (decrement {i+1}) status: {response.status_code}")
        if response.status_code == 200:
             print(f"Response JSON: {response.content.decode()}")

    # 5) POST /carrito/eliminar/ with cart_key
    # Based on views.py, cart_remove needs cart_key in POST or product_id in URL
    # We'll use cart_key in POST
    remove_url = reverse('cart:remove')
    response = client.post(remove_url, {'cart_key': cart_key}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    print(f"Remove status: {response.status_code}")
    if response.status_code == 200:
         print(f"Remove Response JSON: {response.content.decode()}")
    
    final_cart = client.session.get('cart', {})
    print(f"Final Cart session keys: {list(final_cart.keys())}")

if __name__ == '__main__':
    run()
