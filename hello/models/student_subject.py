from django.db import models

class StudentSubject(models.Model):
    INTEREST_CHOICES = [
        (1, '1 - Not Interested'),
        (2, '2 - Slightly Interested'),
        (3, '3 - Moderately Interested'),
        (4, '4 - Very Interested'),
        (5, '5 - Extremely Interested'),
    ]

    student = models.ForeignKey('Student', on_delete=models.CASCADE)
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE)
    interest = models.IntegerField(choices=INTEREST_CHOICES, null=True, blank=True)

    class Meta:
        unique_together = ('student', 'subject')

    def __str__(self):
        return f"{self.student} - {self.subject} ({self.interest})"