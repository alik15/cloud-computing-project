import json as _json
import requests
from django.conf import settings
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt

from .models import UserProfile, STREAMING_SERVICES


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
            UserProfile.objects.get_or_create(user=user)
            login(request, user)
            return redirect("/")
    else:
        form = UserCreationForm()
    return render(request, "register.html", {"form": form})


@login_required
def index(request):
    return render(request, "index.html", {"user": request.user})


@login_required
def user_settings(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "profile":
            new_username = request.POST.get("username", "").strip()
            location = request.POST.get("location", "").strip()
            services = request.POST.getlist("services")

            if new_username and new_username != request.user.username:
                from django.contrib.auth.models import User
                if not User.objects.filter(username=new_username).exclude(pk=request.user.pk).exists():
                    request.user.username = new_username
                    request.user.save()

            profile.location = location
            profile.services = services
            profile.save()
            return redirect("/settings")

        elif action == "password":
            form = PasswordChangeForm(request.user, request.POST)
            if form.is_valid():
                user = form.save()
                update_session_auth_hash(request, user)
                return redirect("/settings")
            return render(request, "settings.html", {
                "password_form": form,
                "profile": profile,
                "all_services": STREAMING_SERVICES,
            })

    password_form = PasswordChangeForm(request.user)
    return render(request, "settings.html", {
        "password_form": password_form,
        "profile": profile,
        "all_services": STREAMING_SERVICES,
    })


def _get_user_services(request):
    try:
        return request.user.profile.services or []
    except Exception:
        return []

# Country code mapping
COUNTRY_MAP = {
    'pakistan': 'pk', 'united states': 'us', 'usa': 'us', 'uk': 'gb',
    'united kingdom': 'gb', 'canada': 'ca', 'australia': 'au',
    'india': 'in', 'germany': 'de', 'france': 'fr', 'uae': 'ae',
}

def _check_streaming(imdb_id, user_services, location=''):
    if not settings.RAPIDAPI_KEY or not imdb_id or not user_services:
        return []
    
    # Default to US if no location or unrecognized
    country = COUNTRY_MAP.get(location.lower().strip(), 'us')
    
    try:
        resp = requests.get(
            f"https://streaming-availability.p.rapidapi.com/shows/{imdb_id}",
            params={"output_language": "en"},
            headers={
                "X-RapidAPI-Key": settings.RAPIDAPI_KEY,
                "X-RapidAPI-Host": "streaming-availability.p.rapidapi.com",
            },
            timeout=5,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        available = []
        streaming = data.get("streamingOptions", {})
        # Only check the user's country
        country_options = streaming.get(country, [])
        for option in country_options:
            service_id = option.get("service", {}).get("id", "")
            if service_id in user_services and service_id not in available:
                available.append(service_id)
        return available
    except Exception as e:
        print(f"[streaming] error: {e}", flush=True)
        return []
@csrf_exempt
def api_proxy(request, path):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "not authenticated"}, status=401)

    # Handle streaming availability check
    if path == "streaming/check":
        imdb_id = request.GET.get("imdb_id", "")
        user_services = _get_user_services(request)
        try:
            location = request.user.profile.location
        except Exception:
            location = ''
        available = _check_streaming(imdb_id, user_services, location)
        return JsonResponse({
            "available_on": available,
            "user_services": user_services,
            "country": COUNTRY_MAP.get(location.lower().strip(), 'us'),
        })
    # Handle user services endpoint
    if path == "user/services":
        user_services = _get_user_services(request)
        return JsonResponse({"services": user_services})

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
