# backend/template_context.py

def base_context(request, user):
    """
    Shared identity context for templates.
    Provides username, role, and business name.
    """

    # Default business label
    business_name = None

    # If user belongs to a business
    if user and user.business:
        business_name = user.business.business_name

    # Fallback (superadmin or no business)
    if not business_name:
        business_name = user.role.capitalize()

    return {
        "request": request,
        "username": user.username,
        "role": user.role,
        "business": business_name,
    }