# app/users/routes/template_helpers.py
from jinja2.sandbox import SandboxedEnvironment
from jinja2 import BaseLoader
from datetime import date, datetime

def _datefmt(value):
    if not value:
        return ""
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")
    return str(value)

def _datefmt_or(value, alt=""):
    s = _datefmt(value)
    return s if s else alt

def jinja_env() -> SandboxedEnvironment:
    env = SandboxedEnvironment(
        loader=BaseLoader(),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["datefmt"] = _datefmt
    env.filters["datefmt_or"] = _datefmt_or
    return env

def build_context(user, agreement_dict: dict, company: dict | None = None):
    # dept and director_of are optional
    dept = getattr(user, "dept", None)
    director_of = None
    try:
        from ...models import Department
        director_of = Department.query.filter_by(manager_id=user.id).first()
    except Exception:
        pass

    return {
        "user": {
            "id": user.id,
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "full_name": f"{(user.first_name or '').strip()} {(user.last_name or '').strip()}".strip(),
            "address": user.address or "",
            "city": user.city or "",
            "email": user.email or "",
            "phone_number": user.phone_number or "",
            "id_number": user.id_number or "",
            "embg": user.embg or "",
            "bank_account": user.bank_account or "",
            "department": getattr(dept, "name", None),
            "director_of": getattr(director_of, "name", None) if director_of else None,
        },
        "agreement": {
            "start_date": agreement_dict.get("start_date"),
            "end_date": agreement_dict.get("end_date"),
            "months": agreement_dict.get("months"),
            "status": agreement_dict.get("status") or "active",
        },
        "company": company or {"name": "Your Company"},
        "today": date.today(),
    }
