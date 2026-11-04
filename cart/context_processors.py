from .cart import Cart
from .shipping import shipping_from_session


def cart(request):
    cart_obj = Cart(request)
    visitor_city = request.session.get("visitor_city")
    shipping_info = shipping_from_session(cart_obj, visitor_city)
    return {
        "cart": cart_obj,
        "shipping_info": shipping_info,
        "visitor_city": visitor_city,
    }
