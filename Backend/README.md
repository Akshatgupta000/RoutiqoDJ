# Routiqo Django Backend

Backend API for **Routiqo – Professional Fleet Dispatch & Route Optimization System**.

Built with **Python 3.12+**, **Django 5.x / 6.x**, **Django REST Framework (DRF)**, and **PyMongo** directly connected to MongoDB.

---

## 🛠️ Tech Stack

- **Framework**: Django & Django REST Framework (DRF)
- **Database**: MongoDB (via PyMongo)
- **Authentication**: Bearer Token Authentication (Sanctum-compatible sha256 tokens) & bcrypt password hashing
- **Geocoding**: OpenStreetMap Nominatim
- **Routing Engine**: Open Source Routing Machine (OSRM)
- **Testing**: `pytest` & `pytest-django` with `mongomock`

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.12+
- MongoDB instance (MongoDB Atlas or local running at `mongodb://localhost:27017`)

### 2. Virtual Environment Setup
```bash
# In the root repository directory
source .venv/bin/activate

# Move to Backend directory
cd Backend
pip install -r requirements.txt
```

### 3. Environment Configuration
```bash
cp .env.example .env
```
Ensure your MongoDB credentials, secret key, and CORS settings are configured in `.env`.

### 4. Database Setup & Checks
```bash
# Apply Django internal tables (for admin/sessions)
python manage.py migrate

# Validate setup
python manage.py check
```

### 5. Start Backend Server
```bash
python manage.py runserver 0.0.0.0:8000
```

Backend will be available at `http://localhost:8000`.

---

## 🧪 Testing

Run automated tests with isolated mock database:
```bash
pytest -v
```
All 31 unit and integration tests run without requiring live network access to MongoDB or external routing servers.
