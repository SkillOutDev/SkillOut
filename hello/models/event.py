from django.db import models


class Event(models.Model):
    name = models.CharField(max_length=200)
    date = models.DateField()
    time = models.TimeField()
    categories = models.ManyToManyField('Category', related_name='events', blank=True)
    short_description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    place = models.CharField(max_length=255)
    source_url = models.URLField(blank=True, null=True)

    def __str__(self):
        return self.name