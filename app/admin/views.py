# -*-coding:utf-8-*-
from flask import render_template, abort, redirect, flash, url_for, request, current_app, make_response, jsonify, Response
from werkzeug import secure_filename
from flask_login import login_required, current_user, login_user
from . import admin
from .. import db
from ..models import User, Role, Post, Permission, Comment, ReComment, Category, registrations, Message, Upvote,Collect, AtUser
from ..decorators import admin_required, permission_required
from flask_login import UserMixin, AnonymousUserMixin

@admin.route('/index', methods=['GET', 'POST'])
@login_required
@admin_required
def index():
    return render_template('admin/index.html',allusers=allusers)

@admin.route('/manage_userlogin/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_userlogin(id):
    user = User.query.get_or_404(id)
    if user.allowlogin:
        user.allowlogin = False
    else:
        user.allowlogin = True
    db.session.add(user)
    db.session.commit()
    return redirect(url_for('admin.index'))


@admin.route('/manage_userdelete/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_userdelete(id):
    user = User.query.get_or_404(id)
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('admin.index'))
