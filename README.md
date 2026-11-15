# App Centre — version Django

Application de gestion de centre de formation, version **100 % Django server-rendered**.
Le frontend Flutter n'est pas inclus dans ce dépôt.

## Fonctionnalités

- Trois rôles : manager, enseignant, élève
- Gestion des centres, classes, groupes, enseignants et élèves
- Emploi du temps et suivi des absences
- Supports de cours, quiz et résultats
- Notifications et demandes d'inscription
- Thème clair / sombre / système
- Envoi d'e-mails via SMTP configurable

## Structure

```text
backend/
  manage.py
  config/       # configuration Django
  accounts/     # utilisateurs et authentification
  centers/      # centres, matières, salles
  people/       # enseignants, élèves, demandes
  academics/    # classes, groupes, emplois du temps
  materials/    # supports de cours
  quizzes/      # quiz et résultats
  web/          # interface web Django (vues, templates, formulaires)
  static/       # CSS et JavaScript
```

## Installation locale

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r backend/requirements.txt
cd backend
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

L'application est accessible sur `http://127.0.0.1:8000/`.

## Comptes de démonstration

Après `python manage.py seed_demo` :

| Rôle | Identifiant | Mot de passe |
| --- | --- | --- |
| Manager | `admin@appcentre.com` | `Admin@123` |
| Enseignant | `aya.kone@appcentre.com` | `Teacher@123` |
| Élève | `adama.toure@appcentre.com` | `Student@123` |

Ces comptes sont réservés à la démonstration. Change les mots de passe avant toute mise en production.

## Configuration de production

La configuration est pilotée par des variables d'environnement. Un modèle est fourni dans
`backend/.env.example`. Le fichier `backend/.env` n'est jamais versionné.

Variables principales :

- `DJANGO_DEBUG=False`
- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DJANGO_EMAIL_*` pour l'envoi réel des e-mails

Exemple d'envoi avec Gmail :

```env
DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DJANGO_EMAIL_HOST=smtp.gmail.com
DJANGO_EMAIL_PORT=587
DJANGO_EMAIL_USE_TLS=True
DJANGO_EMAIL_USE_SSL=False
DJANGO_EMAIL_HOST_USER=adresse@gmail.com
DJANGO_EMAIL_HOST_PASSWORD=mot_de_passe_application
DJANGO_DEFAULT_FROM_EMAIL="AppCentre <adresse@gmail.com>"
```

Le compte PythonAnywhere gratuit n'autorise que le SMTP Gmail. Un compte payant permet
d'utiliser Brevo, Mailjet, SendGrid ou le SMTP de son domaine.

## Tests

```bash
cd backend
python manage.py test
```
