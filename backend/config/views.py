from django.http import JsonResponse
from django.db import connection

def health_check(request):
    """
    Health check endpoint verifying application liveness and database connectivity.
    """
    db_status = "connected"
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            cursor.fetchone()
    except Exception as exc:
        return JsonResponse(
            {
                "status": "unhealthy",
                "database": f"error: {str(exc)}"
            },
            status=503
        )
    return JsonResponse(
        {
            "status": "healthy",
            "database": db_status,
            "service": "public-speaking-workshop"
        },
        status=200
    )
