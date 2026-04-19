import json as _json
import requests
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt


def _connector(path):
    return f"{settings.CONNECTOR_URL}/{path}"


def index(request):
    return render(request, "index.html")


@csrf_exempt
def api_proxy(request, path):
    connector_url = _connector(path)
    params = request.GET.dict()

    try:
        method = request.method.upper()
        print(f"[proxy] {method} {connector_url}", flush=True)

        if method == "GET":
            resp = requests.get(connector_url, params=params, timeout=10)
        elif method == "POST":
            body = _json.loads(request.body or b"{}")
            print(f"[proxy] body={body}", flush=True)
            resp = requests.post(connector_url, json=body, timeout=10)
        elif method == "PATCH":
            body = _json.loads(request.body or b"{}")
            resp = requests.patch(connector_url, json=body, timeout=10)
        elif method == "DELETE":
            resp = requests.delete(connector_url, timeout=10)
        else:
            return HttpResponse(status=405)

        print(f"[proxy] connector responded {resp.status_code}", flush=True)
        return HttpResponse(
            resp.content,
            status=resp.status_code,
            content_type=resp.headers.get("Content-Type", "application/json"),
        )

    except requests.exceptions.ConnectionError as e:
        return JsonResponse({"error": f"Cannot reach connector: {e}"}, status=502)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
