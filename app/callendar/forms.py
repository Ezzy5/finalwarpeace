from datetime import datetime
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, DateTimeField, SelectField, BooleanField, FileField, SelectMultipleField, IntegerField
from wtforms.validators import DataRequired, Optional, Length, ValidationError
from .models import RepeatType

class EventForm(FlaskForm):
    title = StringField("Event name", validators=[DataRequired(), Length(max=255)])
    description = TextAreaField("Description", validators=[Optional()])

    start_dt = DateTimeField("Start", format="%Y-%m-%d %H:%M", validators=[DataRequired()])
    end_dt = DateTimeField("End", format="%Y-%m-%d %H:%M", validators=[DataRequired()])

    timezone = StringField("Time zone", validators=[Optional(), Length(max=64)])

    repeat = SelectField(
        "Repeat",
        choices=[(r.name, r.name.title()) for r in RepeatType],
        default=RepeatType.NONE.name,
        validators=[DataRequired()],
    )

    attendees = SelectMultipleField("Attendees (users)", coerce=int, validators=[Optional()])

    notify_on_responses = BooleanField("Notify when attendees confirm or decline")

    attachment = FileField("Attachment", validators=[Optional()])

    # Reminder: predefined + custom
    reminder_predefined = SelectField(
        "Reminder",
        choices=[
            ("NONE", "No reminder"),
            ("5", "5 minutes before"),
            ("10", "10 minutes before"),
            ("15", "15 minutes before"),
            ("30", "30 minutes before"),
            ("60", "1 hour before"),
        ],
        default="15",
        validators=[DataRequired()],
    )
    reminder_custom = IntegerField("Custom minutes before (overrides preset)", validators=[Optional()])

    def validate_end_dt(self, field):
        if self.start_dt.data and field.data and field.data <= self.start_dt.data:
            raise ValidationError("End time must be after start time.")

class FilterForm(FlaskForm):
    # Combined search + filter bar
    q = StringField("Search", validators=[Optional(), Length(max=255)])

    # Role-like filters
    show_invitations = BooleanField("Invitations")
    i_am_organiser = BooleanField("I am an organiser")
    i_am_participant = BooleanField("I am a participant")
    i_declined = BooleanField("I declined")

    # Period dropdown (any date, yesterday, today, tomorrow, this week, this month, current quarter, next N days, year)
    period = SelectField(
        "Period",
        choices=[
            ("ANY", "Any date"),
            ("YESTERDAY", "Yesterday"),
            ("TODAY", "Current day"),
            ("TOMORROW", "Tomorrow"),
            ("THIS_WEEK", "This week"),
            ("THIS_MONTH", "This month"),
            ("THIS_QUARTER", "Current quarter"),
            ("NEXT_N", "Next N days"),
            ("THIS_YEAR", "This year"),
        ],
        default="THIS_MONTH",
    )
    next_n_days = IntegerField("Next N days", validators=[Optional()])
