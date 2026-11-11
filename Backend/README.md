# Routiqo Django Backend

Backend API for **Routiqo – Professional Fleet Dispatch & Route Optimization System**.

Built with **Python 3.12+**, **Django 5.x / 6.x**, **Django REST Framework (DRF)**, **psycopg 3**, and **PostgreSQL 16**.

---

## 🛠️ Tech Stack

- **Framework**: Django & Django REST Framework (DRF)
- **Database**: PostgreSQL 16 (via psycopg 3 driver and Django ORM)
- **Authentication**: Bearer Token Authentication (Sanctum-compatible sha256 tokens) & legacy bcrypt / PBKDF2 password hashing
- **Geocoding**: OpenStreetMap Nominatim API
- **Routing Engine**: Open Source Routing Machine (OSRM)
- **Testing**: `pytest` & `pytest-django` against PostgreSQL

---

## 🚀 Getting Started

### 1. Prerequisites (Linux Mint / Ubuntu / Debian)
- Python 3.12+
- PostgreSQL 16 (or run via Docker Compose)
- `libpq-dev` / `build-essential`

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
Configure your PostgreSQL credentials, secret key, and CORS settings in `.env`:
```env
DB_ENGINE=django.db.backends.postgresql
DB_HOST=localhost
DB_PORT=5432
DB_NAME=routiqo
DB_USER=routiqo_user
DB_PASSWORD=routiqo_password
```

### 4. Database Setup & Checks
```bash
# Verify database connectivity
python manage.py check_db

# Apply migrations
python manage.py migrate

# Validate Django configuration
python manage.py check
```

### 5. Running the Development Server
```bash
python manage.py runserver 0.0.0.0:8000
```

### 6. Running Tests
```bash
pytest -v
```

---

## 📦 Optional MongoDB Atlas Data Migration

To import existing data from a legacy MongoDB Atlas cluster into your PostgreSQL database:

```bash
export MONGODB_URI="mongodb+srv://user:pass@cluster.mongodb.net/logiroute"
export MONGODB_DATABASE="logiroute"

# Preview records without writing (dry run)
python scripts/migrate_from_mongo.py --dry-run

# Perform migration (idempotent, skips duplicates)
python scripts/migrate_from_mongo.py --skip-existing
```
