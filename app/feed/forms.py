from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SelectMultipleField, HiddenField
from wtforms.validators import DataRequired, Length, Optional

class PostForm(FlaskForm):
    title = StringField("Наслов", validators=[Optional(), Length(max=255)])
    html = TextAreaField("Содржина", validators=[DataRequired()])
    audience_type = SelectField(
        "Видливост",
        choices=[("all", "Сите"), ("sector", "Сектор"), ("users", "Избрани корисници")],
        default="all",
        validators=[DataRequired()],
    )
    audience_id = SelectField("Сектор", choices=[], validators=[Optional()])  # filled dynamically
    user_ids = SelectMultipleField("Корисници", choices=[], validators=[Optional()])
    attachments_manifest = HiddenField()  # JSON with uploaded file metadata (url, name, etc)

class CommentForm(FlaskForm):
    html = TextAreaField("Коментар", validators=[DataRequired()])
