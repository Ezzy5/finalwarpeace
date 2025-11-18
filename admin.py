# create_admin_user.py

from typing import Optional

from app import create_app
from app.extensions import db
from app.models import User, Role, Department

# --- Configuration ---
ADMIN_EMAIL = "admin@primer.com"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "1"

ADMIN_FIRST_NAME = "Admin"
ADMIN_LAST_NAME = "User"
ADMIN_ID_NUMBER = "ADM-0001"

ADMIN_DEPARTMENT_NAME = "Administration"  # Department entity name
ADMIN_PHONE: Optional[str] = ""           # optional
# ----------------------

app = create_app()

def ensure_role(name: str) -> Role:
    role = Role.query.filter_by(name=name).first()
    if not role:
        role = Role(name=name)
        db.session.add(role)
        db.session.commit()
        print(f"Created role: {name}")
    return role

def ensure_department(name: str) -> Department:
    dep = Department.query.filter(db.func.lower(Department.name) == db.func.lower(name)).first()
    if not dep:
        dep = Department(name=name)
        db.session.add(dep)
        db.session.commit()
        print(f"Created department: {name}")
    return dep

def ensure_admin_user(
    email: str,
    username: str,
    password: str,
    first: str,
    last: str,
    id_number: str,
    phone: Optional[str],
    department_name: str,
    admin_role: Role,
    department: Department
) -> User:
    user = User.query.filter_by(email=email).first()

    if user:
        # Update existing user
        user.username = username
        user.first_name = first
        user.last_name = last
        user.phone_number = (phone or None)
        user.id_number = user.id_number or id_number  # don't overwrite an existing id_number
        user.role = admin_role

        # Keep both fields for now (legacy string + FK)
        user.department = department_name
        user.department_id = department.id

        # (Re)Set password
        user.set_password(password)
        db.session.commit()
        print(f"Updated existing admin user: {email}")
    else:
        # Create new user
        user = User(
            username=username,
            email=email,
            first_name=first,
            last_name=last,
            phone_number=(phone or None),
            id_number=id_number,
            role=admin_role,

            # Keep legacy label in sync
            department=department_name,
            # And set the FK membership
            department_id=department.id,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print(f"Created admin user: {email} / password={password}")

    return user

def ensure_department_manager(dep: Department, manager_user: User) -> None:
    changed = False

    # Make the admin user the department director
    if dep.manager_id != manager_user.id:
        dep.manager_id = manager_user.id
        changed = True

    # Ensure the director is also a member (via FK)
    if manager_user.department_id != dep.id:
        manager_user.department_id = dep.id
        changed = True

    if changed:
        db.session.commit()
        print(f"Set '{manager_user.full_name}' as director of '{dep.name}' and ensured membership.")

if __name__ == "__main__":
    with app.app_context():
        # 1) Ensure admin role
        admin_role = ensure_role("admin")

        # 2) Ensure Administration department
        admin_dep = ensure_department(ADMIN_DEPARTMENT_NAME)

        # 3) Ensure admin user
        admin_user = ensure_admin_user(
            email=ADMIN_EMAIL,
            username=ADMIN_USERNAME,
            password=ADMIN_PASSWORD,
            first=ADMIN_FIRST_NAME,
            last=ADMIN_LAST_NAME,
            id_number=ADMIN_ID_NUMBER,
            phone=ADMIN_PHONE,
            department_name=ADMIN_DEPARTMENT_NAME,
            admin_role=admin_role,
            department=admin_dep
        )

        # 4) Make the admin user the director/manager of the Administration department
        ensure_department_manager(admin_dep, admin_user)

        print("Done.")
