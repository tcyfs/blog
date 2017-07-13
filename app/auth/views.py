# -*- coding:utf-8 -*-
from flask import render_template, redirect, request, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from . import auth
from ..models import User,Message
from ..email import send_email
from .. import db
from .forms import LoginForm, RegistrationForm, ChangePasswordForm, PasswordResetForm, PasswordResetRequestForm, ChangeEmailForm


@auth.before_app_request
def before_request():
    if current_user.is_authenticated():
        current_user.ping()
        if not current_user.confirmed \
                and request.endpoint[:5] != 'auth.' and request.endpoint != 'static':
            return redirect(url_for('auth.unconfirmed'))


@auth.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is not None and user.verify_password(form.password.data) and user.allowlogin:
            login_user(user, form.rember_me.data)
            return redirect(request.args.get('next') or url_for('main.index'))
        if not user.allowlogin:
            flash(u'您的账户已被禁止登陆', 'warning')
        else:
            flash(u'邮箱或密码错误', 'warning')
    return render_template('auth/login.html', form=form,Message=Message)


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash(u'你已经退出！', 'info')
    return redirect(url_for('main.index'))


@auth.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(email=form.email.data, username=form.username.data, password=form.password.data)
        db.session.add(user)
        db.session.commit()
        token = user.generate_confirmation_token()
        send_email(user.email, u'确认您的账户', 'auth/email/confirm', user=user, token=token)
        flash(u'确认信息邮件已发送至您的邮箱.', 'info')
        return redirect(url_for('main.index'))
    return render_template('auth/register.html', form=form,Message=Message)


@auth.route('/confirm/<token>')
@login_required
def confirm(token):
    if current_user.confirmed:
        return redirect(url_for('main.index'))
    if current_user.confirm(token):
        flash(u'您已经确认您的账户，谢谢!','success')
    else:
        flash(u'确认链接错误或已过期.','warning')
    return redirect(url_for('main.index'))


@auth.route('/unconfirmed')
def unconfirmed():
    if current_user.is_anonymous() or current_user.confirmed:
        return redirect(url_for('main.index'))
    return render_template('auth/unconfirmed.html',Message=Message)


@auth.route('/confirm')
@login_required
def resend_confirmation():
    token = current_user.generate_confirmation_token()
    send_email(current_user.email, u'确认您的账户', 'auth/email/confirm', user=current_user, token=token)
    flash(u'新的确认邮件已发送至您的邮箱.', 'info')
    return redirect(url_for('main.index'))


@auth.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if current_user.verify_password(form.old_password.data):
            current_user.password = form.password.data
            db.session.add(current_user)
            db.session.commit()
            flash(u'密码修改成功', 'success')
            return redirect(url_for('main.index'))
        else:
            flash(u'密码错误', 'warning')
    return render_template("auth/change_password.html", form=form,Message=Message)


@auth.route('/reset', methods=['GET', 'POST'])
def password_reset_request():
    if not current_user.is_anonymous():
        return redirect(url_for('main.index'))
    form = PasswordResetRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            token = user.generate_reset_token()
            send_email(user.email, u'重置您的密码', 'auth/email/reset_password', user=user, token=token, next=request.args.get('next'))
            flash(u'重置密码邮件已发送至您的邮箱', 'info')
            return redirect(url_for('auth.login'))
        else:
            flash(u'邮箱地址有误，请确认后重新输入', 'warning')
            render_template('auth/reset_password.html', form=form)
    return render_template('auth/reset_password.html', form=form,Message=Message)


@auth.route('/reset<token>', methods=['GET', 'POST'])
def password_reset(token):
    if not current_user.is_anonymous():
        return redirect(url_for('main.index'))
    form = PasswordResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is None:
            return redirect(url_for('main.index'))
        if user.reset_password(token, form.password.data):
            flash(u'密码修改成功.', 'success')
            return redirect(url_for('auth.login'))
        else:
            return redirect(url_for('main.index'))
    return render_template('auth/reset_password.html', form=form,Message=Message)


@auth.route('/change-email', methods=['GET', 'POST'])
@login_required
def change_email_request():
    form = ChangeEmailForm()
    if form.validate_on_submit():
        if current_user.verify_password(form.password.data):
            new_email = form.email.data
            token = current_user.generate_email_change_token(new_email)
            send_email(new_email, u'确认您的邮箱地址', 'auth/email/change_email', user=current_user, token=token)
            flash(u'重置邮箱的邮件已发送至您的新邮箱', 'info')
            return redirect(url_for('main.index'))
        else:
            flash(u'邮箱或密码错误.','warning')
    return render_template('auth/change_email.html', form=form,Message=Message)


@auth.route('/change-email/<token>')
@login_required
def change_email(token):
    if current_user.change_email(token):
        flash(u'邮箱修改成功.', 'success')
    else:
        flash(u'错误请求.', 'warning')
    return redirect(url_for('main.index'))