# AI Personal Finance Management — Backend

Production-ready Django REST Framework backend for personal finance and expense
management, with JWT authentication, MySQL support, group expense splitting and
AI-powered insights.

---

## 1. Features

| Module | What it provides |
|---|---|
| **accounts** | Email-based registration, login/logout, rotated JWT access + refresh tokens, password change, profile, auto-created default categories |
| **categories** | Global defaults + private custom categories (income/expense), filtering, validation |
| **transactions** | Full CRUD, income/expense, search, date/category/amount filters, ordering, pagination, stats action |
| **budgets** | Monthly overall + per-category budgets, utilization percentage, status (`safe`/`warning`/`over`), alerts |
| **dashboard** | Total income/expenses, balance, savings rate, monthly chart series, category spending, recent transactions |
| **reports** | Monthly (with daily trend), yearly (12-month series), category/date-range reports |
| **groups** | Groups, members + roles, shared expenses, equal/custom/percentage splitting, balances, settlement plan, settlement history |
| **ai_assistant** | Auto-categorization, monthly analysis, budget recommendations, unusual-expense detection, natural-language financial queries |

### Safety / design guarantees

- **Secrets from environment only.** `OPENAI_API_KEY`, `SECRET_KEY` and DB credentials are read via `python-decouple`; no key is ever returned by an endpoint.
- **AI never executes SQL.** The model only returns a *validated intent* from a fixed allow-list plus whitelisted parameters. Every number is computed by fixed, user-scoped Django ORM queries in `AIService._execute_intent`. An injected `"DROP TABLE ..."` string is treated as plain text.
- **Graceful degradation.** Without an API key (or when OpenAI errors), every AI endpoint falls back to deterministic, rule-based logic and reports `"source": "fallback"`.
- **Per-user isolation.** Every queryset is scoped to `request.user`; object-level permissions prevent IDOR.
- **Consistent responses.** Success: `{"success": true, "data": ...}`; errors: `{"success": false, "error": {"code", "message", "details"}}`.
- **Validation & error handling.** Serializer validation, model validators, custom `ServiceError`/`ConflictError`, and a global exception handler that never leaks stack traces.
- **API docs.** drf-spectacular Swagger UI / ReDoc, with an exportable `api-schema.yaml`.

---

## 2. Technology

Python 3.12 · Django 6 · Django REST Framework · SimpleJWT · django-filter ·
drf-spectacular · django-cors-headers · mysqlclient · OpenAI SDK · python-decouple

---

## 3. Project structure

```
backend/
├── manage.py
├── requirements.txt
├── .env.example
├── api-schema.yaml                # generated OpenAPI schema
├── config/
│   ├── urls.py                    # /api/v1/... + docs
│   ├── asgi.py / wsgi.py
│   └── settings/
│       ├── base.py                # shared settings (DB, JWT, DRF, CORS, AI, schema)
│       ├── development.py         # DEBUG=True
│       ├── production.py          # hardened, requires real SECRET_KEY
│       └── test.py                # in-memory SQLite, AI disabled
└── apps/
    ├── common/                    # models, mixins, permissions, pagination,
    │                              # responses, exceptions, utils, test helpers
    ├── accounts/                  # models, managers, signals, services, auth views
    ├── categories/                # model, default catalogue, service, viewset
    ├── transactions/              # model, service, filters, viewset
    ├── budgets/                   # model, service, viewset
    ├── dashboard/                 # service + APIViews
    ├── reports/                   # service + APIViews
    ├── groups/                    # models, split/settlement service, nested APIs
    └── ai_assistant/
        ├── services/openai_service.py   # fail-safe SDK wrapper
        └── services/ai_service.py       # categorization, analysis, safe query engine
```

Each app keeps `models.py`, `serializers.py`, `views.py`, `urls.py`,
`services.py` (business logic), `filters.py` (where relevant), `admin.py`,
`migrations/` and `tests/`.

---

## 4. Setup (local development)

```bash
# 1. Create and activate a virtual environment
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create your environment file
copy .env.example .env       # Windows
cp .env.example .env         # macOS / Linux
# Set SECRET_KEY to a long random value.

# 4. Apply migrations (SQLite by default)
python manage.py migrate

# 5. (Optional) create an admin
python manage.py createsuperuser

# 6. Run the server
python manage.py runserver
```

- Swagger UI: <http://127.0.0.1:8000/api/docs/>
- ReDoc: <http://127.0.0.1:8000/api/redoc/>
- Raw OpenAPI schema: <http://127.0.0.1:8000/api/schema/>
- Django admin: <http://127.0.0.1:8000/admin/>

Regenerate the committed schema after changing endpoints:

```bash
python manage.py spectacular --file api-schema.yaml
```

---

## 5. MySQL configuration

Install the driver (`mysqlclient` is in `requirements.txt`; on Windows use a
wheel, on Debian/Ubuntu `sudo apt install libmysqlclient-dev`), create a database:

```sql
CREATE DATABASE finance_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'finance_user'@'localhost' IDENTIFIED BY 'strong-password';
GRANT ALL PRIVILEGES ON finance_db.* TO 'finance_user'@'localhost';
FLUSH PRIVILEGES;
```

Then set in `.env`:

```ini
DB_ENGINE=mysql
DB_NAME=finance_db
DB_USER=finance_user
DB_PASSWORD=strong-password
DB_HOST=127.0.0.1
DB_PORT=3306
```

Apply migrations and run with production settings:

```bash
python manage.py migrate --settings=config.settings.production
python manage.py runserver --settings=config.settings.production
```

`base.py` automatically selects the MySQL backend when `DB_ENGINE=mysql`, and
falls back to SQLite otherwise (used for local development and tests).

---

## 6. Running tests

```bash
# All 46 tests (forced in-memory SQLite, OpenAI disabled)
python manage.py test --settings=config.settings.test

# A single module
python manage.py test apps.groups --settings=config.settings.test
```

Coverage includes auth/JWT, category defaults & isolation, transaction CRUD /
filters / stats, budget utilization & alerts, dashboard, all report types,
group splitting / balances / settlements, and AI fallbacks + injection safety.

---

## 7. Authentication flow

All endpoints except register/login/refresh require
`Authorization: Bearer <access_token>`.

### Register

`POST /api/v1/auth/register`

```json
{
  "email": "user@example.com",
  "password": "StrongPass123!",
  "password2": "StrongPass123!",
  "first_name": "Ada"
}
```

Response `201`:

```json
{
  "success": true,
  "data": {
    "id": 1,
    "email": "user@example.com",
    "full_name": "Ada",
    "first_name": "Ada",
    "currency": "USD",
    "timezone": "UTC",
    "is_verified": false,
    "date_joined": "2026-11-16T10:00:00Z"
  },
  "message": "Account created successfully."
}
```

### Login

`POST /api/v1/auth/login` — `{ "email": "...", "password": "..." }`

Response `200`:

```json
{
  "success": true,
  "data": {
    "refresh": "eyJhbGciOiJIUzI1NiJ9...",
    "access": "eyJhbGciOiJIUzI1NiJ9...",
    "user": { "id": 1, "email": "user@example.com", "full_name": "Ada" }
  },
  "message": "Logged in successfully."
}
```

Other auth endpoints: `POST /auth/refresh`, `POST /auth/logout`
(`{"refresh": "..."}` — blacklists the token), `GET|PATCH /auth/profile`,
`POST /auth/change-password`.

Access tokens live 60 minutes; refresh tokens 7 days and rotate on use
(configurable in `.env`).

---

## 8. REST endpoints

### Categories — `/api/v1/categories/`
| Method | Path | Description |
|---|---|---|
| GET | `/` | List visible categories (defaults + own). Filters: `type`, `is_default`, `name`, `search` |
| POST | `/` | Create custom category `{name, type, icon?, color?}` |
| GET/PATCH/DELETE | `/{id}/` | Retrieve / update / delete (defaults cannot be deleted) |

### Transactions — `/api/v1/transactions/`
| Method | Path | Description |
|---|---|---|
| GET | `/` | Paginated list. Filters: `type`, `category`, `date_from`, `date_to`, `year`, `month`, `min_amount`, `max_amount`, `payment_method`, `is_recurring`; `search`, `ordering`, `page_size` |
| POST | `/` | Create (see sample below) |
| GET/PATCH/DELETE | `/{id}/` | Retrieve / update / delete |
| GET | `/stats/?date_from=&date_to=` | Income, expenses, balance, count |

Create sample:

```json
{
  "category_id": 3,
  "type": "expense",
  "amount": "25.50",
  "description": "Lunch",
  "date": "2026-11-16",
  "payment_method": "card",
  "notes": "Team lunch"
}
```

Response `201` (excerpt):

```json
{
  "success": true,
  "data": {
    "id": 12,
    "category": { "id": 3, "name": "Food & Dining", "type": "expense" },
    "type": "expense",
    "amount": "25.50",
    "description": "Lunch",
    "date": "2026-11-16",
    "source": "manual"
  }
}
```

### Budgets — `/api/v1/budgets/`
CRUD at `/`; `GET /summary/?year=&month=` and `GET /alerts/?year=&month=`.

Create: `{ "amount": "500.00", "month": 11, "year": 2026, "alert_threshold": "80.00" }`
(omit `category_id` for an overall budget, or supply a category id for a
category budget). Detail includes computed `spent`, `remaining`,
`utilization_percentage`, `status`, `is_alert`.

### Dashboard — `/api/v1/dashboard/`
- `GET /summary` → totals, balance, savings rate, this-month change
- `GET /monthly-spending/?months=12` → chart-ready series
- `GET /category-spending/?year=&month=` → ranked category breakdown
- `GET /recent-transactions/?limit=5`

Sample `/summary` data:

```json
{
  "total_income": "5000.00",
  "total_expenses": "1250.00",
  "available_balance": "3750.00",
  "savings_rate": 75.0,
  "this_month": { "income": "5000.00", "expenses": "1250.00", "net": "3750.00", "transaction_count": 12, "expense_change_pct": -8.2 },
  "active_budget_alerts": 1
}
```

### Reports — `/api/v1/reports/`
- `GET /monthly/?year=&month=` → summary + categories + daily trend
- `GET /yearly/?year=` → summary + 12 monthly buckets + categories
- `GET /category/?start_date=&end_date=&type=expense` → per-category totals

### Groups — `/api/v1/groups/`
| Method | Path | Description |
|---|---|---|
| GET/POST | `/` | List my groups / create `{name, description?, currency?}` |
| GET/PATCH/DELETE | `/{id}/` | Retrieve / update / delete (admin) |
| GET | `/{id}/balances` | Net balance per member (+ = owed to them) |
| GET | `/{id}/settlement-plan` | Minimal set of suggested payments |
| GET/POST | `/{id}/members` | List / add `{email, role?}` (admin only) |
| DELETE | `/{id}/members/{member_id}` | Remove member |
| GET/POST | `/{id}/expenses` | List / create + split shared expense |
| GET/DELETE | `/{id}/expenses/{expense_id}` | Retrieve / delete |
| GET/POST | `/{id}/settlements` | List / record `{to_user, amount, note?}` |

Create a shared expense:

```json
{
  "description": "Weekend dinner",
  "amount": "90.00",
  "date": "2026-11-16",
  "paid_by": 1,
  "split_type": "equal"
}
```

`split_type` may be `equal`, `custom` (send `shares: [{user_id, amount}, ...]`
summing to the total) or `percentage` (send `shares: [{user_id, percentage}, ...]`
summing to 100). Rounding remainders are assigned deterministically so shares
always add up to the exact amount.

### AI assistant — `/api/v1/ai/`
| Method | Path | Body / description |
|---|---|---|
| POST | `/categorize` | `{description, amount?}` → suggested category + confidence |
| POST | `/analyze-spending` | `{year?, month?}` → summary, insights, suggestions |
| POST | `/recommend-budgets` | no body → per-category recommendations |
| GET | `/unusual-expenses` → flagged recent transactions |
| POST | `/query` | `{question}` → safe answer from ORM data |

Sample query:

```json
{ "question": "How much did I spend on food this month?" }
```

```json
{
  "success": true,
  "data": {
    "intent": "spending_by_category",
    "parameters": { "month": 11, "year": 2026 },
    "answer": "You spent 40.00 in 2026-11; the largest category was Food & Dining at 40.00 (100.0%).",
    "source": "fallback"
  }
}
```

`source` is `"ai"` when OpenAI responded, otherwise `"fallback"`.

---

## 9. Default categories

Created automatically for every new user:

- **Expense** — Food & Dining, Groceries, Transportation, Housing & Rent, Bills & Utilities, Shopping, Entertainment, Healthcare, Education, Travel, Personal Care, Other Expense
- **Income** — Salary, Freelance, Investments, Business, Gifts, Other Income

---

## 10. Configuration reference (`.env`)

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | insecure dev value | Django/JWT signing — **must set in production** |
| `DEBUG` | `True` | Debug mode |
| `ALLOWED_HOSTS` | localhost,... | Comma-separated hosts |
| `DB_ENGINE` | `sqlite` | `sqlite` or `mysql` |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | — | MySQL connection |
| `JWT_ACCESS_TOKEN_LIFETIME_MINUTES` | `60` | Access token TTL |
| `JWT_REFRESH_TOKEN_LIFETIME_DAYS` | `7` | Refresh token TTL |
| `CORS_ALLOWED_ORIGINS` | localhost:3000 | Frontend origins |
| `OPENAI_API_KEY` | empty | Server-side only; empty disables AI calls |
| `OPENAI_MODEL` | `gpt-4o-mini` | Chat model |
| `API_PAGE_SIZE` | `20` | Default page size |
| `THROTTLE_ANON` / `THROTTLE_USER` | `200/hour`, `2000/hour` | Rate limits |

Production settings additionally require a non-placeholder `SECRET_KEY`.
