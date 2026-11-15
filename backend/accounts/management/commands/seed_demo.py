import random

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from accounts.models import User
from centers.models import Center, Subject, ClassRoom
from people.models import Teacher, Student, StudentRequest
from academics.models import Classe, ClassGroup, Schedule
from materials.models import SubjectMaterial
from quizzes.models import Quiz, QuizQuestion, QuizOption, QuizResult


class Command(BaseCommand):
    help = 'Seed demo data for AppCentre'

    def handle(self, *args, **options):
        self.stdout.write('Seeding data...')

        user, _ = User.objects.get_or_create(
            email='admin@appcentre.com',
            defaults={
                'username': 'admin@appcentre.com',
                'first_name': 'Kouassi',
                'last_name': 'Jean',
                'role': 'manager',
                'is_staff': True,
                'is_superuser': True,
            },
        )
        user.set_password('Admin@123')
        user.save()

        center, _ = Center.objects.get_or_create(
            name='Centre Excellence Cocody',
            defaults={
                'address': 'Rue des Palmiers, Cocody, Abidjan',
                'phone': '+225 07 08 09 10',
                'email': 'contact@excellence-cocody.ci',
                'manager': user,
            },
        )

        subjects_data = [
            ('Mathématiques', 'Maths'),
            ('Physique-Chimie', 'Physique'),
            ('Français', 'Français'),
            ('Anglais', 'Anglais'),
            ('Histoire-Géo', 'Histoire'),
        ]
        subjects = {}
        for name, code in subjects_data:
            s, _ = Subject.objects.get_or_create(
                name=name, center=center,
                defaults={'description': f'Cours de {name}'},
            )
            subjects[name] = s

        rooms_data = [
            ('Salle A', 35, 'Salle principale'),
            ('Salle B', 30, 'Salle informatique'),
            ('Salle C', 25, 'Laboratoire'),
            ('Amphi', 60, 'Grand amphithéâtre'),
        ]
        rooms = {}
        for name, cap, desc in rooms_data:
            r, _ = ClassRoom.objects.get_or_create(
                name=name, center=center,
                defaults={'capacity': cap, 'description': desc},
            )
            rooms[name] = r

        teacher_users = []
        teacher_data = [
            ('Aya', 'Koné', 'aya.kone@appcentre.com', 'Mathématiques'),
            ('Moussa', 'Diallo', 'moussa.diallo@appcentre.com', 'Physique-Chimie'),
            ('Fatou', 'Bamba', 'fatou.bamba@appcentre.com', 'Français'),
        ]
        for fn, ln, email, spec in teacher_data:
            tu, _ = User.objects.get_or_create(
                email=email,
                defaults={
                    'username': email,
                    'first_name': fn,
                    'last_name': ln,
                    'role': 'teacher',
                },
            )
            tu.set_password('Teacher@123')
            tu.save()

            teacher, _ = Teacher.objects.get_or_create(
                user=tu, center=center,
                defaults={'speciality': spec},
            )
            teacher.classrooms.add(random.choice(list(rooms.values())))
            teacher_users.append(teacher)

        students_data = [
            ('Adama', 'Touré', '+225 05 12 34 56 01', '+225 01 23 45 67 01'),
            ('Aminata', 'Sissoko', '+225 05 12 34 56 02', '+225 01 23 45 67 02'),
            ('Ibrahim', 'Camara', '+225 05 12 34 56 03', '+225 01 23 45 67 03'),
            ('Fatima', 'Diallo', '+225 05 12 34 56 04', '+225 01 23 45 67 04'),
            ('Oumar', 'Bah', '+225 05 12 34 56 05', '+225 01 23 45 67 05'),
            ('Sekou', 'Keita', '+225 05 12 34 56 06', '+225 01 23 45 67 06'),
            ('Mariam', 'Cissé', '+225 05 12 34 56 07', '+225 01 23 45 67 07'),
            ('Jean', 'Konan', '+225 05 12 34 56 08', '+225 01 23 45 67 08'),
        ]
        students = []
        for fn, ln, phone, pphone in students_data:
            s, _ = Student.objects.get_or_create(
                first_name=fn, last_name=ln, center=center,
                defaults={
                    'phone': phone,
                    'parent_phone': pphone,
                    'registration_type': 'manual',
                    'status': 'approved',
                },
            )
            if s.user_id is None:
                student_email = f'{slugify(fn)}.{slugify(ln)}@appcentre.com'
                user, _ = User.objects.get_or_create(
                    email=student_email,
                    defaults={
                        'username': student_email,
                        'first_name': fn,
                        'last_name': ln,
                        'phone': phone,
                        'role': 'student',
                    },
                )
                user.set_password('Student@123')
                user.save()
                s.user = user
                s.save(update_fields=['user'])
            students.append(s)

        pending_student, _ = Student.objects.get_or_create(
            first_name='Awa',
            last_name='Ouattara',
            center=center,
            defaults={
                'phone': '+225 05 99 88 77 66',
                'parent_phone': '+225 01 11 22 33 44',
                'registration_type': 'self_request',
                'status': 'pending',
            },
        )
        StudentRequest.objects.get_or_create(
            student=pending_student,
            center=center,
            defaults={
                'message': 'Je souhaite rejoindre le centre pour des cours de mathématiques.',
            },
        )

        class_data = [
            ('6ème A', 'Mathématiques', teacher_data[0][0], 'Salle A'),
            ('5ème B', 'Physique-Chimie', teacher_data[1][0], 'Salle C'),
            ('3ème A', 'Français', teacher_data[2][0], 'Salle B'),
        ]
        groups = {}
        for name, subj, _, room_name in class_data:
            teacher = random.choice(teacher_users)
            classe, _ = Classe.objects.get_or_create(name=name, center=center)
            g, _ = ClassGroup.objects.get_or_create(
                name=name, center=center,
                defaults={
                    'classe': classe,
                    'subject': subjects[subj],
                    'teacher': teacher,
                    'classroom': rooms[room_name],
                },
            )
            groups[name] = g

        for student in students[:6]:
            group_name = random.choice(list(groups.keys()))
            student.class_group = groups[group_name]
            student.classe = groups[group_name].classe
            student.save(update_fields=['class_group', 'classe'])

        days_hours = [
            (0, '08:00', '10:00'),
            (1, '10:00', '12:00'),
            (2, '08:00', '10:00'),
            (3, '14:00', '16:00'),
            (4, '10:00', '12:00'),
        ]
        for g in groups.values():
            for day, start, end in days_hours[:3]:
                Schedule.objects.get_or_create(
                    class_group=g, day_of_week=day,
                    defaults={
                        'start_time': start,
                        'end_time': end,
                        'classroom': g.classroom,
                    },
                )

        for g in groups.values():
            teacher = g.teacher
            if not teacher:
                continue
            q, _ = Quiz.objects.get_or_create(
                title=f'Quiz {g.subject.name} - Chapitre 1',
                teacher=teacher,
                defaults={
                    'description': f'Quiz de {g.subject.name} sur le premier chapitre',
                    'duration_minutes': 30,
                    'total_points': 10,
                },
            )
            q.class_groups.add(g)
            SubjectMaterial.objects.get_or_create(
                title=f'Support {g.subject.name} - Chapitre 1',
                teacher=teacher,
                class_group=g,
                defaults={
                    'subject': g.subject,
                    'center': center,
                    'description': f'Fiche de cours de {g.subject.name}.',
                    'external_link': 'https://example.com/support',
                },
            )

            questions_data = [
                ('Quelle est la racine carrée de 144 ?', 'qcm', 5, [
                    ('10', False), ('11', False), ('12', True), ('14', False),
                ]),
                ('La Terre tourne autour du Soleil.', 'true_false', 3, [
                    ('Vrai', True), ('Faux', False),
                ]),
                ('Citez la formule de Pythagore.', 'short_answer', 2, [
                    ('a² + b² = c²', True),
                ]),
            ]
            for i, (text, qtype, pts, opts) in enumerate(questions_data, 1):
                qq, _ = QuizQuestion.objects.get_or_create(
                    quiz=q, order=i,
                    defaults={
                        'question_text': text,
                        'question_type': qtype,
                        'points': pts,
                    },
                )
                if qtype != 'short_answer':
                    for opt_text, is_correct in opts:
                        QuizOption.objects.get_or_create(
                            question=qq, option_text=opt_text,
                            defaults={'is_correct': is_correct},
                        )

        self.stdout.write(self.style.SUCCESS(
            f'Done! {User.objects.count()} users, '
            f'{Center.objects.count()} centers, '
            f'{Teacher.objects.count()} teachers, '
            f'{Student.objects.count()} students, '
            f'{ClassGroup.objects.count()} groups, '
            f'{Quiz.objects.count()} quizzes'
        ))
