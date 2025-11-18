from app import create_app
from app.extensions import db
from app.models import Department, DepartmentPermission
from app.permissions import PERMISSION_CATALOG

app = create_app()
with app.app_context():
    for d in Department.query.all():
        existing = {
            p.permission
            for p in DepartmentPermission.query.filter_by(department_id=d.id).all()
        }
        for code in PERMISSION_CATALOG.keys():
            if code not in existing:
                db.session.add(DepartmentPermission(
                    department_id=d.id,
                    permission=code,
                    allowed=False
                ))
    db.session.commit()
    print("Seeded missing department permissions.")
from app import create_app

app = create_app()

if __name__ == "__main__":
	app.run(debug=True)