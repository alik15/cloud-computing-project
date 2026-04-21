import json as _json
import requests
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm

def _connector(path):
    return f"{settings.CONNECTOR_URL}/{path}"


def health(request):
    return HttpResponse("ok")


def register(request):
    if request.user.is_authenticated:
        return redirect("/")
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("/")
    else:
        form = UserCreationForm()
    return render(request, "register.html", {"form": form})

@login_required
def index(request):
    return render(request, "index.html", {"user": request.user})


@csrf_exempt
def api_proxy(request, path):
    """
    Proxy all /api/<path> calls to the Go connector.
    Passes the logged-in username as X-User-ID header so the
    connector can scope movies per user.
    """
    if not request.user.is_authenticated:
        return JsonResponse({"error": "not authenticated"}, status=401)

    connector_url = _connector(path)
    params = request.GET.dict()
    headers = {
        "Content-Type": "application/json",
        "X-User-ID": str(request.user.id),
        "X-Username": request.user.username,
    }

    try:
        method = request.method.upper()

        if method == "GET":
            resp = requests.get(connector_url, params=params, headers=headers, timeout=10)
        elif method == "POST":
            body = _json.loads(request.body or b"{}")
            resp = requests.post(connector_url, json=body, headers=headers, timeout=10)
        elif method == "PATCH":
            body = _json.loads(request.body or b"{}")
            resp = requests.patch(connector_url, json=body, headers=headers, timeout=10)
        elif method == "DELETE":
            resp = requests.delete(connector_url, headers=headers, timeout=10)
        else:
            return HttpResponse(status=405)

        return HttpResponse(
            resp.content,
            status=resp.status_code,
            content_type=resp.headers.get("Content-Type", "application/json"),
        )

    except requests.exceptions.ConnectionError as e:
        return JsonResponse({"error": f"Cannot reach connector: {e}"}, status=502)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
