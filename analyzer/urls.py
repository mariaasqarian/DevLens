
from django.urls import path
from . import views

urlpatterns = [
    path("", views.analyze_code, name="analyze_code"),
]
# این کد چه کاری انجام می‌دهد؟
# - path برای تعریف مسیرهای سایت استفاده می‌شود.
# - views فایل views.py را وارد می‌کند.
# - path("", ...) مسیر اصلی اپلیکیشن را به تابع analyze_code متصل می‌کند.