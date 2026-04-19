from django.urls import path, re_path
from . import views

urlpatterns = [
    re_path(r"^api/(?P<path>.+)$", views.api_proxy, name="api_proxy"),
    re_path(r"^.*$", views.index, name="index"),
]
