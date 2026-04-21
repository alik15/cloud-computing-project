from django.urls import re_path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    re_path(r"^login$",  auth_views.LoginView.as_view(template_name="login.html"), name="login"),
    re_path(r"^logout$", auth_views.LogoutView.as_view(), name="logout"),
    re_path(r"^register$", views.register, name="register"),
    re_path(r"^health$", views.health, name="health"),
    re_path(r"^api/(?P<path>.+)$", views.api_proxy, name="api_proxy"),
    re_path(r"^.*$", views.index, name="index"),
]
