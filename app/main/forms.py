# -*- coding:utf-8 -*-
from flask_wtf import Form
from wtforms import StringField, SubmitField, TextField, BooleanField, SelectField, TextAreaField,SelectMultipleField
from wtforms.validators import DataRequired, Length, Email, Regexp, NoneOf
from wtforms import ValidationError
from flask_pagedown.fields import PageDownField
from ..models import Role, User, Category


class EditProfileForm(Form):
    nickname = StringField(u'修改昵称', validators=[Length(0, 64)], render_kw={'placeholder': u'请不要经常使用，以后可能限制此功能'})
    name = StringField(u'真实姓名', validators=[Length(0, 64)])
    location = StringField(u'位置', validators=[Length(0, 64)])
    about_me = TextField(u'自我介绍')
    submit = SubmitField(u'提交')


class EditProfileAdminForm(Form):
    email = StringField(u'邮箱', validators=[DataRequired(), Length(1, 64), Email()])
    username = StringField(u'用户名', validators=[DataRequired(), Length(1, 64)])
    confirmed = BooleanField(u'确认')
    role = SelectField(u'角色', coerce=int)
    name = StringField(u'真实姓名', validators=[Length(0, 64)])
    location = StringField(u'位置', validators=[Length(0, 64)])
    about_me = TextAreaField(u'关于我')
    submit = SubmitField(u'提交')

    def __init__(self, user, *args, **kwargs):
        super(EditProfileAdminForm, self).__init__(*args, **kwargs)
        self.role.choices = [(role.id, role.name) for role in Role.query.order_by(Role.name).all()]
        self.user = user

    def validate_email(self, field):
        if field.data != self.user.email and User.query.filter_by(email=field.data).first():
            raise ValidationError(u'邮箱已被注册')

    def validate_username(self, field):
        if field.data != self.user.username and User.query.filter_by(username=field.data).first():
            raise ValidationError(u'用户名已存在')


class PostForm(Form):
    tag = SelectMultipleField(u'选择文章标签(可多选)', coerce=int)
    customtag = StringField(u'手动添加更多标签',validators=[Length(0, 10)],render_kw={'placeholder': u'请输入少于10个文字'})
    body = TextAreaField(u'发表博文', validators=[DataRequired()], render_kw={'placeholder': u'此刻在想什么呢？'})
    submit1 = SubmitField(u'发表')
    def __init__(self, *args, **kwargs):
        super(PostForm, self).__init__(*args, **kwargs)
        self.tag.choices = [(1, 'Python'),(2,"Web"),(3,"Flask"),(4,u"数据库"),(5,u"杂记"),(6,"Dota")]
    def validate_customtag(self, field):
        if field.data.lower() in ["python","web","flask",u"数据库",u"杂记","dota"]:
            raise ValidationError(u'列表中存在相似标签，你可以直接选择')

class CommentForm(Form):
    body = TextAreaField('', validators=[DataRequired()], render_kw={'placeholder': u'写下你的评论'})
    submit = SubmitField(u'提交')


class ReCommentForm(Form):
    body = StringField('',validators=[DataRequired()],render_kw={'placeholder': u'回复'})
    submit1 = SubmitField(u'提交')

class MessageForm(Form):
    body = StringField('', validators=[DataRequired()], render_kw={'placeholder': u'回复'})
    submit = SubmitField(u'发送')