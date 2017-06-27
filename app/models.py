# -*-coding:utf-8-*-
import sys
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from markdown import markdown
import bleach
from flask import current_app, request
from flask_login import UserMixin, AnonymousUserMixin
from . import db, login_manager
import hashlib
import flask_whooshalchemyplus as whooshalchemy
from jieba.analyse import ChineseAnalyzer



class Permission(object):
    FOLLOW = 0x01
    COMMENT = 0x02
    WRITE_ARTICLES = 0x04
    MODERATE_COMMENTS = 0x08
    ADMINISTER = 0x80


class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    default = db.Column(db.Boolean, default=False, index=True)
    permissions = db.Column(db.Integer)
    users = db.relationship('User', backref='role', lazy='dynamic')

    @staticmethod
    def insert_roles():
        roles = {'User': (Permission.FOLLOW | Permission.COMMENT | Permission.WRITE_ARTICLES, True),
                 'Moderator': (Permission.FOLLOW | Permission.COMMENT | Permission.WRITE_ARTICLES | Permission.MODERATE_COMMENTS, False),
                 'Administrator': (0xff, False)}
        for r in roles:
            role = Role.query.filter_by(name=r).first()
            if role is None:
                role = Role(name=r)
            role.permissions = roles[r][0]
            role.default = roles[r][1]
            db.session.add(role)
        db.session.commit()

    def __repr__(self):
        return '<Role %r>' % self.name


class Follow(db.Model):
    __tablename__ = 'follows'
    follower_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    followed_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(64), unique=True, index=True)
    username = db.Column(db.String(64), unique=True, index=True)
    password_hash = db.Column(db.String(128))
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    confirmed = db.Column(db.Boolean, default=False)
    name = db.Column(db.String(64))
    photo = db.Column(db.String(64)) #touxiang
    location = db.Column(db.String(64))
    about_me = db.Column(db.Text())
    member_since = db.Column(db.DateTime(), default=datetime.utcnow)
    last_seen = db.Column(db.DateTime(), default=datetime.utcnow)
    avatar_hash = db.Column(db.String(32))
    posts = db.relationship('Post', backref='author', lazy='dynamic')
    followed = db.relationship('Follow', foreign_keys=[Follow.follower_id], backref=db.backref('follower', lazy='joined'),
                               lazy='dynamic', cascade='all, delete-orphan')
    followers = db.relationship('Follow', foreign_keys=[Follow.followed_id], backref=db.backref('followed', lazy='joined'),
                                lazy='dynamic', cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='author', lazy='dynamic')
    recomments = db.relationship('ReComment', backref='author', lazy='dynamic')
    upvotes = db.relationship('Upvote', backref='author', lazy='dynamic')
    collects = db.relationship('Collect', backref='author', lazy='dynamic')
    messages = db.relationship('Message', backref='author', lazy='dynamic',primaryjoin='Message.author_id==User.id')
    messageds = db.relationship('Message', backref='sendto', lazy='dynamic',primaryjoin='Message.sendto_id==User.id')

    @staticmethod
    def generate_fake(count=100):
        from sqlalchemy.exc import IntegrityError
        from random import seed
        import forgery_py

        seed()
        for i in range(count):
            u = User(email=forgery_py.internet.email_address(),
                     username=forgery_py.internet.user_name(True),
                     password=forgery_py.lorem_ipsum.word(),
                     confirmed=True,
                     name=forgery_py.name.full_name(),
                     location=forgery_py.address.city(),
                     about_me=forgery_py.lorem_ipsum.sentence(),
                     member_since=forgery_py.date.date(True))
            db.session.add(u)
            db.session.commit()
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()

    @staticmethod
    def add_self_follows():
        for user in User.query.all():
            if not user.is_following(user):
                user.follow(user)
                db.session.add(user)
                db.session.commit()

    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        
        if self.role is None:
            if self.email == current_app.config['FLASKY_ADMIN']:
                self.role = Role.query.filter_by(permissions=0xff).first()
            if self.role is None:
                self.role = Role.query.filter_by(default=True).first()
        if self.email is not None and self.avatar_hash is None:
            self.avatar_hash = hashlib.md5(self.email.encode('utf-8')).hexdigest()
        self.followed.append(Follow(followed=self))

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_confirmation_token(self, expiration=3600):
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps({'confirm': self.id})

    def confirm(self, token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return False
        if data.get('confirm') != self.id:
            return False
        self.confirmed = True
        db.session.add(self)
        db.session.commit()
        return True

    def generate_reset_token(self, expiration=3600):
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps({'reset': self.id})

    def reset_password(self, token, new_password):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return False
        if data.get('reset') != self.id:
            return False
        self.password = new_password
        db.session.add(self)
        db.session.commit()
        return True

    def generate_email_change_token(self, new_email, expiration=3600):
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps({'change_email':self.id, 'new_email':new_email})

    def change_email(self, token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return False
        if data.get('change_email') != self.id:
            return False
        new_email = data.get('new_email')
        if new_email is None:
            return False
        if self.query.filter_by(email=new_email).first() is not None:
            return False
        self.email = new_email
        self.avatar_hash = hashlib.md5(self.email.encode('utf-8')).hexdigest()
        db.session.add(self)
        db.session.commit()
        return True

    def can(self, permissions):
        return self.role is not None and (self.role.permissions & permissions) == permissions

    def is_administrator(self):
        return self.can(Permission.ADMINISTER)

    def ping(self):
        self.last_seen = datetime.utcnow()
        db.session.add(self)
        db.session.commit()

    def gravatar(self, size=100, default='identicon', rating='g'):
        if request.is_secure:
            url = 'http://secure.gravatar.com/avatar'
        else:
            url = 'http://gravatar.com/avatar'
        hash = self.avatar_hash or hashlib.md5(self.email.encode('utf-8')).hexdigest()
        return '{url}/{hash}?s={size}&d={default}&r={rating}'.format(url=url, hash=hash, size=size, default=default, rating=rating)

    def follow(self, user):
        if not self.is_following(user):
            f = Follow(follower=self, followed=user)
            db.session.add(f)
            db.session.commit()
            
    def unfollow(self, user):
        f = self.followed.filter_by(followed_id=user.id).first()
        if f:
            db.session.delete(f)
            db.session.commit()

    def is_following(self, user):
        return self.followed.filter_by(followed_id=user.id).first() is not None

    def is_followed_by(self, user):
        return self.followers.filter_by(follower_id=use.id).first() is not None

    @property
    def followed_posts(self):
        return Post.query.join(Follow, Follow.followed_id == Post.author_id).filter(Follow.follower_id == self.id)
    def __repr__(self):
        return '<User %r>' % self.username


class AnonymousUser(AnonymousUserMixin):
    def can(self, permissions):
        return False

    def is_administrator(self):
        return False

login_manager.anonymous_user = AnonymousUser


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))




class Post(db.Model):
    __tablename__ = 'posts'
    __searchable__ = ['body']
    __analyzer__ = ChineseAnalyzer()  
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text)
    body_html = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    comments = db.relationship('Comment', backref='post', lazy='dynamic')
    recomments = db.relationship('ReComment', backref='post', lazy='dynamic')
    upvotes = db.relationship('Upvote', backref='post', lazy='dynamic')
    collect = db.relationship('Collect', backref='post', lazy='dynamic')

    @staticmethod
    def generate_fake(count=100):
        from random import seed, randint
        import forgery_py

        seed()
        user_count = User.query.count()
        for i in range(count):
            u = User.query.offset(randint(0, user_count - 1)).first()
            p = Post(body=forgery_py.lorem_ipsum.sentences(randint(1, 5)),
                     timestamp=forgery_py.date.date(True),
                     author=u)
            db.session.add(p)
            db.session.commit()

    @staticmethod
    def on_changed_body(target, value, oldvalue, initiator):
        allowed_tags = ['a', 'abbr', 'acronym', 'b', 'blockquote', 'code', 'em', 'i', 'li', 'ol', 'pre', 'strong',
                        'ul', 'h1', 'h2', 'h3', 'p','img','embed']
        attrs={'*': ['class', 'style'],'img':['src', 'alt'],'a':'href','embed':['src','width','height','type']}
        styles = ['height', 'width'] 
        target.body_html = bleach.linkify(bleach.clean(markdown(value, output_format='html'), tags=allowed_tags,
                                                       attributes=attrs,styles=styles, strip=True))
db.event.listen(Post.body, 'set', Post.on_changed_body)


class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text)
    body_html = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    sendto_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    confirmed = db.Column(db.Boolean, default=False)
    author_delete = db.Column(db.Boolean, default=False)
    sendto_delete = db.Column(db.Boolean, default=False)

    @staticmethod
    def on_changed_body(target, value, oldvalue, initiator):
        allowed_tags = ['a', 'abbr', 'b', 'code', 'em', 'i', 'strong','img']
        attrs={'*': ['class', 'style'],'img':['src', 'alt'],'a':'href','embed':['src','width','height','type']}
        styles = ['height', 'width'] 
        target.body_html = bleach.linkify(bleach.clean(markdown(value, output_format='html'), tags=allowed_tags,
                                                       attributes=attrs,styles=styles,strip=True))
db.event.listen(Message.body, 'set', Message.on_changed_body)


class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text)
    body_html = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    disabled = db.Column(db.Boolean)
    confirmed = db.Column(db.Boolean, default=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'))
    recomments = db.relationship('ReComment', backref='comment', lazy='dynamic')

    @staticmethod
    def on_changed_body(target, value, oldvalue, initiator):
        allowed_tags = ['a', 'abbr', 'b', 'code', 'em', 'i', 'strong','img']
        attrs={'*': ['class', 'style'],'img':['src', 'alt'],'a':'href','embed':['src','width','height','type']}
        styles = ['height', 'width'] 
        target.body_html = bleach.linkify(bleach.clean(markdown(value, output_format='html'), tags=allowed_tags,
                                                       attributes=attrs,styles=styles,strip=True))
db.event.listen(Comment.body, 'set', Comment.on_changed_body)

class ReComment(db.Model):
    __tablename__ = 'recomments'
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text)
    body_html = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    disabled = db.Column(db.Boolean)
    reply_id = db.Column(db.Integer)
    reply_type = db.Column(db.Text, default='recomment')
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    comment_id = db.Column(db.Integer, db.ForeignKey('comments.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'))

    @staticmethod
    def on_changed_body(target, value, oldvalue, initiator):
        allowed_tags = ['a', 'abbr', 'b', 'code', 'em', 'i', 'strong','img']
        attrs={'*': ['class', 'style'],'img':['src', 'alt'],'a':'href','embed':['src','width','height','type']}
        styles = ['height', 'width']
        target.body_html = bleach.linkify(bleach.clean(markdown(value, output_format='html'), tags=allowed_tags,
                                                       attributes=attrs,styles=styles,strip=True))
db.event.listen(ReComment.body, 'set', ReComment.on_changed_body)


registrations = db.Table('registrations',
                        db.Column('category_id', db.Integer, db.ForeignKey('categorys.id')),
                        db.Column('post_id', db.Integer, db.ForeignKey('posts.id'))
                        )
class Category(db.Model):
    __tablename__ = 'categorys'
    __searchable__ = ['name']
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    posts = db.relationship('Post',secondary=registrations,backref=db.backref('categorys', lazy='dynamic'),lazy='dynamic')


    @staticmethod
    def insert_categorys():
        categorylist = ["Python","Web","Flask",u"数据库",u"杂记","Dota"]
        for category in  categorylist:
            postcategory=Category.query.filter_by(name=category).first()
            if postcategory is None:
                postcategory=Category(name=category)
                db.session.add(postcategory)
            db.session.commit()

class Upvote(db.Model):
    __tablename__ = 'upvotes'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'))


class Collect(db.Model):
    __tablename__ = 'collects'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'))