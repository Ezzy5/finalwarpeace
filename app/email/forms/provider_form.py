# app/email/forms/provider_form.py
from flask_wtf import FlaskForm
from wtforms import RadioField, SubmitField
from wtforms.validators import DataRequired


class ProviderForm(FlaskForm):
    provider = RadioField(
        "Select Provider",
        choices=[
            ("gmail", "Gmail"),
            ("outlook", "Outlook / Microsoft 365"),
            ("yahoo", "Yahoo"),
            ("custom", "Custom (Company)"),
        ],
        validators=[DataRequired()],
        render_kw={"class": "form-check-input"},
    )

    submit = SubmitField("Continue")
