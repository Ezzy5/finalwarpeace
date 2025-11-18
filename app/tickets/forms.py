from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectMultipleField, SelectField, DateField, IntegerField, FileField
from wtforms.validators import DataRequired, Optional, Length
from app.tickets.models import TicketStatus, TicketPriority
from flask_wtf.file import FileAllowed

class TicketForm(FlaskForm):
    title = StringField("Наслов", validators=[DataRequired(), Length(max=200)])
    description = TextAreaField("Опис", validators=[Optional()])
    assignees = SelectMultipleField("Доделено на", coerce=int, validators=[Optional()])
    departments = SelectMultipleField("Оддели", coerce=int, validators=[Optional()])
    priority = SelectField("Приоритет",
                           choices=[(TicketPriority.LOW.value, "Low"),
                                    (TicketPriority.MEDIUM.value, "Medium"),
                                    (TicketPriority.HIGH.value, "High"),
                                    (TicketPriority.URGENT.value, "Urgent")],
                           validators=[DataRequired()],
                           default=TicketPriority.MEDIUM.value)
    due_date = DateField("Рок", validators=[Optional()])
    parent_ticket_id = IntegerField("Родител тикет", validators=[Optional()])
    initial_attachment = FileField(
        "Прилог (слика, опционално)",
        validators=[Optional(), FileAllowed(["png", "jpg", "jpeg", "gif", "webp", "bmp", "pdf", "doc", "docx", "xls", "xlsx", "txt"], "Неподдржан тип на датотека.")]
    )

class CommentForm(FlaskForm):
    body = TextAreaField("Коментар", validators=[Optional()])
    status_change_to = SelectField(
        "Промени статус",
        coerce=str,
        choices=[
            ("", "—"),
            (TicketStatus.IN_PROGRESS.value, "In Progress"),
            (TicketStatus.COMPLETED.value, "Completed"),
        ],
        validators=[Optional()],
        default="",   # ✅ no auto-change
    )
    attachment = FileField("Прилог", validators=[Optional()])
