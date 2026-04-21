from django.test import TestCase, RequestFactory
from unittest.mock import patch, MagicMock
from app.views import health, api_proxy, index

# Run locally:
#   cd frontend && python manage.py test app --verbosity=2
#
# No database required — all dependencies are mocked


class HealthTests(TestCase):

    def test_health_returns_200(self):
        factory = RequestFactory()
        request = factory.get('/health')
        response = health(request)
        self.assertEqual(response.status_code, 200)

    def test_health_returns_ok(self):
        factory = RequestFactory()
        request = factory.get('/health')
        response = health(request)
        self.assertEqual(response.content, b'ok')


class IndexViewTests(TestCase):

    def test_index_redirects_unauthenticated(self):
        factory = RequestFactory()
        request = factory.get('/')
        request.user = MagicMock()
        request.user.is_authenticated = False
        response = index(request)
        self.assertEqual(response.status_code, 302)

    def test_index_returns_200_when_authenticated(self):
        factory = RequestFactory()
        request = factory.get('/')
        request.user = MagicMock()
        request.user.is_authenticated = True
        request.user.username = 'testuser'
        response = index(request)
        self.assertEqual(response.status_code, 200)


class ApiProxyTests(TestCase):

    def _make_request(self, method='GET', path='/api/movies', body=None, authenticated=True):
        factory = RequestFactory()
        if method == 'GET':
            request = factory.get(path)
        elif method == 'POST':
            request = factory.post(path, data=body, content_type='application/json')
        elif method == 'DELETE':
            request = factory.delete(path)
        elif method == 'PATCH':
            request = factory.patch(path, data=body, content_type='application/json')
        elif method == 'PUT':
            request = factory.put(path)

        request.user = MagicMock()
        request.user.is_authenticated = authenticated
        request.user.id = 1
        request.user.username = 'testuser'
        return request

    def test_returns_401_when_not_authenticated(self):
        request = self._make_request(authenticated=False)
        response = api_proxy(request, 'movies')
        self.assertEqual(response.status_code, 401)

    @patch('app.views.requests.get')
    def test_get_returns_connector_response(self, mock_get):
        mock_get.return_value.content = b'[]'
        mock_get.return_value.status_code = 200
        mock_get.return_value.headers = {'Content-Type': 'application/json'}

        request = self._make_request()
        response = api_proxy(request, 'movies')
        self.assertEqual(response.status_code, 200)

    @patch('app.views.requests.get')
    def test_forwards_user_id_header(self, mock_get):
        mock_get.return_value.content = b'[]'
        mock_get.return_value.status_code = 200
        mock_get.return_value.headers = {'Content-Type': 'application/json'}

        request = self._make_request()
        api_proxy(request, 'movies')

        call_headers = mock_get.call_args[1]['headers']
        self.assertEqual(call_headers['X-User-ID'], '1')

    @patch('app.views.requests.get')
    def test_forwards_username_header(self, mock_get):
        mock_get.return_value.content = b'[]'
        mock_get.return_value.status_code = 200
        mock_get.return_value.headers = {'Content-Type': 'application/json'}

        request = self._make_request()
        api_proxy(request, 'movies')

        call_headers = mock_get.call_args[1]['headers']
        self.assertEqual(call_headers['X-Username'], 'testuser')

    @patch('app.views.requests.post')
    def test_post_returns_connector_status(self, mock_post):
        mock_post.return_value.content = b'{"id":1,"title":"Test"}'
        mock_post.return_value.status_code = 201
        mock_post.return_value.headers = {'Content-Type': 'application/json'}

        request = self._make_request(method='POST', body='{"title":"Test","watched":false}')
        response = api_proxy(request, 'movies')
        self.assertEqual(response.status_code, 201)

    @patch('app.views.requests.delete')
    def test_delete_returns_connector_status(self, mock_delete):
        mock_delete.return_value.content = b'{"deleted":"1"}'
        mock_delete.return_value.status_code = 200
        mock_delete.return_value.headers = {'Content-Type': 'application/json'}

        request = self._make_request(method='DELETE')
        response = api_proxy(request, 'movies/1')
        self.assertEqual(response.status_code, 200)

    @patch('app.views.requests.get')
    def test_returns_502_when_connector_unreachable(self, mock_get):
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError('connector down')

        request = self._make_request()
        response = api_proxy(request, 'movies')
        self.assertEqual(response.status_code, 502)

    def test_returns_405_for_unsupported_method(self):
        request = self._make_request(method='PUT')
        response = api_proxy(request, 'movies')
        self.assertEqual(response.status_code, 405)
