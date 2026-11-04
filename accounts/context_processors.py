from .dashboard_data import user_display_name


def account(request):
    if request.user.is_authenticated:
        return {"user_display_name": user_display_name(request.user)}
    return {}
