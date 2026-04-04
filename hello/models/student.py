from django.db import models
from django.contrib.auth.models import User

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    subjects = models.ManyToManyField('Subject', through='StudentSubject', related_name='students')
    # Add any additional fields for student here, e.g., student_id, etc.

    def __str__(self):
        return self.user.username