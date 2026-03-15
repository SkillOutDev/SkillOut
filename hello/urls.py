# The urls.py file is where you specify patterns to route different URLs to their appropriate views.
# The code below contains one route to
# map root URL of the app ("") to the views.home function that you just added to hello/views.py:

from django.urls import path
from hello import views

urlpatterns = [
    path("", views.home, name="home"),
    path("add-student/", views.add_student, name="add_student"),
    path("add-category/", views.add_category, name="add_category"),
    path("add-subject/", views.add_subject, name="add_subject"),
    path("add-interest/", views.add_subject_interest, name="add_subject_interest"),
    path("student/<int:student_id>/subjects/", views.get_student_subjects, name="get_student_subjects"),
    path("api/scrape-text/", views.scrape_text, name="scrape-text"),
    path("api/import-subjects/", views.import_subjects_with_categories, name="import-subjects"),
    path("api/scrape-import-assign/", views.scrape_import_and_assign_subjects, name="scrape-import-assign"),
    path("api/scrape-events/", views.scrape_events, name="scrape-events"),
    # API endpoint to get the latest subjects
    path('api/get-latest-subjects/', views.get_latest_subjects, name='get-latest-subjects'),
    path('api/get-latest-events/', views.get_latest_events, name='get-latest-events'),
]
