import json
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from .models import Student, Category, Subject, StudentSubject
import json

# Create your views here.

def home(request):
    return HttpResponse("Hello, world!")

def hello_there(request, name):
    print(request.build_absolute_uri()) #optional
    return render(
        request,
        'hello/hello_there.html',
        {
            'name': name,
            'date': datetime.now()
        }
    )

@csrf_exempt
def add_student(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            email = data.get('email')
            password = data.get('password')
            first_name = data.get('first_name', '')
            last_name = data.get('last_name', '')

            if not username or not password:
                return JsonResponse({'error': 'Username and password are required'}, status=400)

            if User.objects.filter(username=username).exists():
                return JsonResponse({'error': 'Username already exists'}, status=400)

            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )

            student = Student.objects.create(user=user)

            return JsonResponse({
                'message': 'Student created successfully',
                'student_id': student.id,
                'user_id': user.id
            }, status=201)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def add_category(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name')

            if not name:
                return JsonResponse({'error': 'Name is required'}, status=400)

            if Category.objects.filter(name=name).exists():
                return JsonResponse({'error': 'Category already exists'}, status=400)

            category = Category.objects.create(name=name)

            return JsonResponse({
                'message': 'Category created successfully',
                'category_id': category.id,
                'name': category.name
            }, status=201)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def add_subject(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name')
            category_id = data.get('category_id')

            if not name:
                return JsonResponse({'error': 'Name is required'}, status=400)

            if Subject.objects.filter(name=name).exists():
                return JsonResponse({'error': 'Subject already exists'}, status=400)

            category = None
            if category_id:
                try:
                    category = Category.objects.get(id=category_id)
                except Category.DoesNotExist:
                    return JsonResponse({'error': 'Category not found'}, status=400)

            subject = Subject.objects.create(name=name, category=category)

            return JsonResponse({
                'message': 'Subject created successfully',
                'subject_id': subject.id,
                'name': subject.name,
                'category_id': category.id if category else None,
                'category_name': category.name if category else None
            }, status=201)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def add_subject_interest(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            student_id = data.get('student_id')
            subject_id = data.get('subject_id')
            interest = data.get('interest')

            if not all([student_id, subject_id, interest]):
                return JsonResponse({'error': 'student_id, subject_id, and interest are required'}, status=400)

            try:
                interest = int(interest)
                if interest not in [1, 2, 3, 4, 5]:
                    return JsonResponse({'error': 'Interest must be between 1 and 5'}, status=400)
            except ValueError:
                return JsonResponse({'error': 'Interest must be a number'}, status=400)

            try:
                student = Student.objects.get(id=student_id)
            except Student.DoesNotExist:
                return JsonResponse({'error': 'Student not found'}, status=404)

            try:
                subject = Subject.objects.get(id=subject_id)
            except Subject.DoesNotExist:
                return JsonResponse({'error': 'Subject not found'}, status=404)

            student_subject, created = StudentSubject.objects.update_or_create(
                student=student,
                subject=subject,
                defaults={'interest': interest}
            )

            return JsonResponse({
                'message': 'Interest level updated successfully' if not created else 'Interest level set successfully',
                'student_id': student_id,
                'subject_id': subject_id,
                'interest': interest,
                'created': created
            }, status=201)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Method not allowed'}, status=405)

def get_student_subjects(request, student_id):
    if request.method == 'GET':
        try:
            student = Student.objects.get(id=student_id)
        except Student.DoesNotExist:
            return JsonResponse({'error': 'Student not found'}, status=404)

        student_subjects = StudentSubject.objects.filter(student=student).select_related('subject__category')

        subjects_data = []
        for ss in student_subjects:
            subject = ss.subject
            subjects_data.append({
                'subject_id': subject.id,
                'name': subject.name,
                'category_id': subject.category.id if subject.category else None,
                'category_name': subject.category.name if subject.category else None,
                'interest': ss.interest,
                'interest_description': dict(StudentSubject.INTEREST_CHOICES)[ss.interest]
            })

        return JsonResponse({
            'student_id': student_id,
            'student_username': student.user.username,
            'subjects': subjects_data,
            'total_subjects': len(subjects_data)
        }, status=200)

    else:
        return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def add_category(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name')

            if not name:
                return JsonResponse({'error': 'Name is required'}, status=400)

            if Category.objects.filter(name=name).exists():
                return JsonResponse({'error': 'Category already exists'}, status=400)

            category = Category.objects.create(name=name)

            return JsonResponse({
                'message': 'Category created successfully',
                'category_id': category.id,
                'name': category.name
            }, status=201)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def add_subject(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name')
            category_id = data.get('category_id')

            if not name:
                return JsonResponse({'error': 'Name is required'}, status=400)

            if Subject.objects.filter(name=name).exists():
                return JsonResponse({'error': 'Subject already exists'}, status=400)

            category = None
            if category_id:
                try:
                    category = Category.objects.get(id=category_id)
                except Category.DoesNotExist:
                    return JsonResponse({'error': 'Category not found'}, status=400)

            subject = Subject.objects.create(name=name, category=category)

            return JsonResponse({
                'message': 'Subject created successfully',
                'subject_id': subject.id,
                'name': subject.name,
                'category_id': category.id if category else None,
                'category_name': category.name if category else None
            }, status=201)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def scrape_text(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST is allowed."}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    url = (payload.get("url") or "").strip()
    if not url:
        return JsonResponse({"error": "Field 'url' is required."}, status=400)
    if not (url.startswith("http://") or url.startswith("https://")):
        return JsonResponse({"error": "URL must start with http:// or https://."}, status=400)

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        return JsonResponse({"error": f"Failed to fetch URL: {exc}"}, status=400)

    soup = BeautifulSoup(response.text, "html.parser")

    for element in soup(["script", "style", "noscript"]):
        element.extract()

    text = soup.get_text(separator=" ", strip=True)[:60000]

    output_dir = Path(settings.BASE_DIR) / "scraped_text"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "latest_scrape.txt"
    output_file.write_text(text, encoding="utf-8")

    return JsonResponse(
        {
            "message": "Scraped text saved successfully.",
            "file": str(output_file.relative_to(settings.BASE_DIR)),
            "characters": len(text),
        }
    )