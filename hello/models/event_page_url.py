from django.db import models


class EventPageUrl(models.Model):
    SOURCE_CHOICES = [
        ("litexpo", "Litexpo"),
        ("meetup", "Meetup"),
        ("kaveikti", "Kaveikti"),
        ("other", "Other"),
    ]

    url = models.URLField(unique=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    city = models.CharField(max_length=100, blank=True)
    last_seen = models.DateTimeField(auto_now=True)
    last_scraped = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.url