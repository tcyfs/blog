from flask import render_template
from . import main
from ..models import User, Role, Post, Permission, Comment, ReComment, Category,registrations, Message


@main.app_errorhandler(403)
def forbidden(e):
    return render_template('403.html',Message=Message), 403


@main.app_errorhandler(404)
def page_not_found(e):
    return render_template('404.html',Message=Message), 404


@main.app_errorhandler(500)
def internal_server_error(e):
    return render_template('500.html',Message=Message), 500