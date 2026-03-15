from django.contrib import admin
from .models import Student, Subject, StudentSubject, Event, EventPageUrl

# Register your models here.

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('user',)
    # Add more customizations as needed

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(StudentSubject)
class StudentSubjectAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'interest')
    list_filter = ('interest',)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'date', 'time', 'price', 'place')
    list_filter = ('date', 'categories')
    search_fields = ('name', 'place', 'short_description')


@admin.register(EventPageUrl)
class EventPageUrlAdmin(admin.ModelAdmin):
    list_display = ('source', 'city', 'url', 'last_seen', 'last_scraped', 'is_active')
    list_filter = ('source', 'city', 'is_active')
    search_fields = ('url', 'city')
