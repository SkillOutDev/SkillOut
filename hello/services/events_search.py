"""Business logic for searching and filtering events by categories and student interests.

Refactored for reduced complexity and improved maintainability.
"""

from hello.models import Event, Subject, StudentSubject


def _normalize_category_name(category_or_name):
    """Extract and normalize a category name from various input types.
    
    Returns normalized name (lowercase, stripped) or None if invalid.
    """
    if not category_or_name:
        return None
    
    # If it's a string, normalize directly
    if isinstance(category_or_name, str):
        return category_or_name.strip().lower()
    
    # If it's an object with a name attribute
    if hasattr(category_or_name, 'name'):
        name = category_or_name.name
        if name:
            return name.strip().lower()
    
    return None


def _resolve_subject(subject):
    """Resolve subject input to a Subject object.
    
    Accepts: Subject instance, subject ID (int), or subject name (str).
    Returns: Subject object with category preloaded, or None if not found.
    """
    if isinstance(subject, Subject):
        return subject
    
    if isinstance(subject, int):
        return Subject.objects.filter(id=subject).select_related("category").first()
    
    if isinstance(subject, str):
        return Subject.objects.filter(name__iexact=subject.strip()).select_related("category").first()
    
    return None


def _get_subject_category_name(subject_obj):
    """Safely extract and normalize category name from subject.
    
    Returns normalized category name or None if subject/category invalid.
    """
    if not subject_obj or not subject_obj.category:
        return None
    
    return _normalize_category_name(subject_obj.category.name)


def _event_matches_category(event, category_name):
    """Check if event has a category matching the given category name.
    
    Args:
        event: Event object
        category_name: Normalized category name (lowercase, stripped)
    
    Returns: True if any event category matches, False otherwise
    """
    return any(
        _normalize_category_name(c.name) == category_name
        for c in event.categories.all()
    )


def search_events_by_subject_category(subject):
    """Find events whose categories match the given subject's category.

    Accepts a Subject instance, subject id, or subject name. Returns a list of Event objects.
    """
    subject_obj = _resolve_subject(subject)
    if not subject_obj:
        return []
    
    category_name = _get_subject_category_name(subject_obj)
    if not category_name:
        return []
    
    events = Event.objects.prefetch_related("categories").order_by("-date", "-time")
    return [event for event in events if _event_matches_category(event, category_name)]


def _extract_category_from_student_subject(student_subject):
    """Extract category object from StudentSubject record.
    
    Returns: Category object or None if subject or category missing.
    """
    if not student_subject.subject:
        return None
    return student_subject.subject.category


def _update_category_interest_map(map_dict, category, interest_level):
    """Update category interest map with new interest level if higher.
    
    Only updates if the new interest is greater than the current value.
    """
    if not category:
        return
    
    category_name = _normalize_category_name(category.name)
    if not category_name:
        return
    
    current_interest = map_dict.get(category_name, 0)
    if interest_level > current_interest:
        map_dict[category_name] = interest_level


def build_student_category_interest_map(student):
    """Build a mapping of category names to the student's highest interest level in that category."""
    student_subjects = StudentSubject.objects.filter(
        student=student,
        interest__gt=0,
    ).select_related("subject__category")

    category_interest_map = {}
    for student_subject in student_subjects:
        category = _extract_category_from_student_subject(student_subject)
        _update_category_interest_map(category_interest_map, category, student_subject.interest)

    return category_interest_map


def _get_matching_interests_for_event(event, category_interest_map):
    """Find all interest levels in an event that match the category map.
    
    Returns: List of matching interest levels for event's categories.
    """
    matching = []
    for event_category in event.categories.all():
        category_name = _normalize_category_name(event_category.name)
        if category_name and category_name in category_interest_map:
            matching.append(category_interest_map[category_name])
    return matching


def _rank_similar_events(events, category_interest_map):
    """Rank events by highest matching interest level.
    
    Returns: List of events sorted by interest level (descending).
    """
    similar_events = []
    
    for event in events:
        matching_interests = _get_matching_interests_for_event(event, category_interest_map)
        if matching_interests:
            similar_events.append((max(matching_interests), event))
    
    similar_events.sort(key=lambda item: item[0], reverse=True)
    return [event for _, event in similar_events]


def get_events_similar_to_student_subjects(student):
    """Return events that match categories of student's subjects with interest > 0.

    Events are ranked by the highest matching interest level, while preserving the
    existing newest-first ordering as a tie-breaker.

    Returns a tuple of (events, category_names) where events are sorted by interest
    and category_names are the categories used for matching.
    """
    base_events = Event.objects.prefetch_related("categories").order_by("-date", "-time")
    category_interest_map = build_student_category_interest_map(student)
    
    similar_events = _rank_similar_events(base_events, category_interest_map)
    return similar_events, sorted(category_interest_map.keys())

