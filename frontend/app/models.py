from django.db import models
from django.contrib.auth.models import User

STREAMING_SERVICES = [
    ('netflix',     'Netflix'),
    ('prime',       'Amazon Prime'),
    ('disney',      'Disney+'),
    ('hbo',         'HBO Max'),
    ('apple',       'Apple TV+'),
    ('hulu',        'Hulu'),
    ('peacock',     'Peacock'),
    ('paramount',   'Paramount+'),
    ('crunchyroll', 'Crunchyroll'),
    ('mubi',        'Mubi'),
]

class UserProfile(models.Model):
    user     = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    location = models.CharField(max_length=100, blank=True, default='')
    services = models.JSONField(default=list)

    def __str__(self):
        return f"{self.user.username}'s profile"
