# -*-coding:utf-8-*-
import os
import json
from datetime import datetime,timedelta
import random
import urllib
from flask import render_template, abort, redirect, flash, url_for, request, current_app, make_response,jsonify
from .. import photos
from werkzeug import secure_filename
from flask_login import login_required, current_user, login_user
from . import main
from .forms import EditProfileForm, EditProfileAdminForm, PostForm, CommentForm, ReCommentForm,MessageForm
from ..auth import forms
from ..email import send_email
from .. import db
from ..models import User, Role, Post, Permission, Comment, ReComment, Category,registrations, Message
from ..decorators import admin_required, permission_required
from qiniu import Auth, put_file, etag, urlsafe_base64_encode,put_data
import qiniu.config
import time
from sqlalchemy.sql import or_

class UploadToQiniu():
    def __init__(self, file,domian_name='http://oqytm3mqj.bkt.clouddn.com', bucket_name='flaskblog',  expire=3600):
        self.access_key = 'TvQoGbSnVvStgs6brjwPzCS3nADzEQ_kjSzHGotm'
        self.secret_key = 'Q--6LAxGsiySHpNxcxBiGh1Ud79-0LvzT3jPpvUu'
        self.bucket_name = bucket_name
        self.domian_name = domian_name
        self.file = file
        self.expire = expire

    def upload(self):
        q = Auth(self.access_key, self.secret_key)
        user = current_user
        ext = self.file.filename.split('.')[-1]
        time_ = str(time.time()).replace('.', '')
        k = time_ + '_' + str(user.id) + '.' + ext 
        token = q.upload_token(self.bucket_name, k, self.expire)
        return put_data(token, k, self.file.read())
@main.route('/upfile/<username>',methods = ['GET','POST'])
def upfile(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        abort(404)
    posts = user.posts.order_by(Post.timestamp.desc()).all()
    if request.method == 'POST' and 'photo' in request.files:
        try:
            u = UploadToQiniu(request.files['photo'])  
            ret, inf = u.upload()
            key = ret['key']
            file_url = u.domian_name+'/'+key
            current_user.photo = file_url
            db.session.add(current_user)
            db.session.commit()
            return render_template('user.html', user=user, posts=posts,Message=Message)
            
        except:
            flash(u'上传失败，请确认上传文件是图片','warning')
            return render_template('upload.html',Message=Message)
    return render_template('upload.html',Message=Message)
@main.route('/about_web')
def about_web():
    return render_template('about_web.html')
@main.route('/', methods=['GET', 'POST'])
def index():
    for i in Category.query.all():
        if i.posts.count() == 0:
            if i.name in ['Python','Flask',u'数据库','Dota','Web',u'杂记']:
                continue
            db.session.delete(i)
            db.session.commit()

    form1 = PostForm()
    form2 = forms.LoginForm()
    form3 = forms.RegistrationForm()
    if current_user.can(Permission.WRITE_ARTICLES) and form1.submit1.data and form1.validate_on_submit():
        post = Post(body=form1.body.data, author=current_user._get_current_object())
        db.session.add(post)
        db.session.commit()
        for i in form1.tag.data:
            tag = Category.query.get(i)
            tag.posts.append(post)
            db.session.add(tag)
            db.session.commit()
        if form1.customtag.data.strip():
            tag=Category(name=form1.customtag.data)
            tag.posts.append(post)
            db.session.add(tag)
            db.session.commit()

        flash(u'提交文章成功.', 'info')
        return redirect(url_for(".index"))
    if form2.submit2.data and form2.validate_on_submit():
        user = User.query.filter_by(email=form2.email.data).first()
        if user is not None and user.verify_password(form2.password.data):
            login_user(user, form2.rember_me.data)
            return redirect(request.args.get('next') or url_for('main.index'))
        flash(u'邮箱或密码错误0.0', 'warning')
    if form3.submit3.data and form3.validate_on_submit():
        user = User(email=form3.email.data, username=form3.username.data, password=form3.password.data)
        db.session.add(user)
        db.session.commit()
        token = user.generate_confirmation_token()
        send_email(user.email, u'确认您的账户', 'auth/email/confirm', user=user, token=token)
        flash(u'确认信息邮件已发送至您的邮箱.', 'info')
        return redirect(url_for('auth.login'))
    page = request.args.get('page', 1, type=int)
    show_followed = False
    if current_user.is_authenticated():
        show_followed = bool(request.cookies.get('show_followed', ''))
    if show_followed:
        query = current_user.followed_posts
    else:
        query = Post.query
    pagination = query.order_by(Post.timestamp.desc()).paginate(page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
                                                                     error_out=False)
    posts = pagination.items
    return render_template('index.html', form1=form1, form2=form2,form3=form3, posts=posts, show_followed=show_followed, pagination=pagination, Category=Category,Message=Message)


@main.route('/user/<username>')
def user(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        abort(404)
    posts = user.posts.order_by(Post.timestamp.desc()).all()
    return render_template('user.html', user=user, posts=posts,Message=Message)


@main.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.location = form.location.data
        current_user.about_me = form.about_me.data
        db.session.add(current_user)
        db.session.commit()
        flash(u'个人信息修改成功', 'success')
        return redirect(url_for('.user', username=current_user.username))
    form.name.data = current_user.name
    form.location.data = current_user.location
    form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', form=form,Message=Message)


@main.route('/edit-profile/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_profile_admin(id):
    user = User.query.get_or_404(id)
    form = EditProfileAdminForm(user=user)
    if form.validate_on_submit():
        user.email = form.email.data
        user.username = form.username.data
        user.confirmed = form.confirmed.data
        user.role = Role.query.get(form.role.data)
        user.name = form.name.data
        user.location = form.location.data
        user.about_me = form.about_me.data
        db.session.add(user)
        db.session.commit()
        flash(u'信息修改成功.','success')
        return redirect(url_for('.user', username=user.username))
    form.email.data = user.email
    form.username.data = user.username
    form.confirmed.data = user.confirmed
    form.role.data = user.role_id
    form.name.data = user.name
    form.location.data = user.location
    form.about_me.data = user.about_me
    return render_template('edit_profile.html', form=form, user=user,Message=Message)


@main.route('/post/<int:id>', methods=['GET', 'POST'])
def post(id):
    post = Post.query.get_or_404(id)
    form = CommentForm()
    if form.submit.data and form.validate_on_submit():
        comment = Comment(body=form.body.data, post=post, author=current_user._get_current_object())
        db.session.add(comment)
        db.session.commit()
        flash(u'评论提交成功','success')
        return redirect(url_for('.post', id=post.id, page=-1))

    page = request.args.get('page', 1, type=int)
    if page == -1:
        page = (post.comments.count()-1) // current_app.config['FLASKY_COMMENTS_PER_PAGE']+1
    pagination = post.comments.order_by(Comment.timestamp.desc()).paginate(page, per_page=current_app.config['FLASKY_COMMENTS_PER_PAGE'],
                                                                          error_out=False)
    comments = pagination.items

    return render_template('post.html', posts=[post], form=form, comments=comments, pagination=pagination, ReComment=ReComment, Category=Category,Message=Message)

@main.route('/recomment/<int:id>', methods=['POST'])
@login_required
def recomment(id):
    comment = Comment.query.get_or_404(id)
    post = Post.query.get_or_404(comment.post_id)
    data = json.loads(request.form.get('data'))
    a = data['a']
    if a.strip() == '':
        return 'input nothing'
    recomment = ReComment(body=a, post=post,comment=comment,author=current_user._get_current_object(),reply_id=comment.id)

    db.session.add(recomment)
    db.session.commit()
    return jsonify(result=a)
    #return redirect(url_for('.post', id=comment.post_id))

@main.route('/reply/<int:id>', methods=['POST'])
@login_required
def reply(id):
    recomment = ReComment.query.get_or_404(id)
    comment = Comment.query.get_or_404(recomment.comment_id)
    post = Post.query.get_or_404(comment.post_id)
    data = json.loads(request.form.get('data'))
    a = data['a']
    if a.strip() == '':
        return 'input nothing'
    reply = ReComment(body=a, comment=comment,post=post,author=current_user._get_current_object(),reply_id=recomment.id,reply_type="reply")
    db.session.add(reply)
    db.session.commit()
    
    return jsonify(result=a)

@main.route('/delete_post/<int:id>', methods=['GET','POST'])
@login_required
def delete_post(id):
    post = Post.query.get_or_404(id)
    if current_user != post.author and not current_user.can(Permission.ADMINISTER):
        abort(403)
    db.session.delete(post)
    db.session.commit()
    flash(u'文章已删除', 'danger')
    return redirect(url_for('main.index'))

@main.route('/delete_recomment/<int:id>', methods=['GET','POST'])
@login_required
def delete_recomment(id):
    recomment = ReComment.query.get_or_404(id)
    replys = ReComment.query.filter_by(reply_id=id).all()
    for reply in replys:
        delreply =  ReComment.query.get_or_404(reply.id)
        db.session.delete(delreply)
        db.session.commit()
    comment = Comment.query.get_or_404(recomment.comment_id)
    db.session.delete(recomment)
    db.session.commit()
    try:
        flash(u'回复已删除', 'danger')
        return redirect(url_for('.post', id=comment.post_id))
    except:
        flash(u'此评论文章不存在', 'danger')
        return redirect(url_for('main.index'))

@main.route('/delete_comment/<int:id>', methods=['GET','POST'])
@login_required
def delete_comment(id):
    comment = Comment.query.get_or_404(id)
    db.session.delete(comment)
    db.session.commit()
    try:
        flash(u'回复已删除', 'danger')
        return redirect(url_for('.post', id=comment.post_id))
    except:
        flash(u'此评论文章不存在', 'danger')
        return redirect(url_for('main.index'))



@main.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    post = Post.query.get_or_404(id)
    if current_user != post.author and not current_user.can(Permission.ADMINISTER):
        abort(403)
    form = PostForm()
    if form.validate_on_submit():
        post.body = form.body.data
        db.session.add(post)
        db.session.commit()
        for i in form.tag.data:
            tag = Category.query.get(i)
            if tag in post.categorys.all():
                post.categorys.remove(tag)
                post.categorys.append(tag)
            post.categorys.append(tag)
            db.session.add(post)
            db.session.commit()
        if form.customtag.data.strip():
            tag=Category(name=form.customtag.data)
            tag.posts.append(post)
            db.session.add(tag)
            db.session.commit()
        flash(u'文章修改成功!','success')
        return redirect(url_for('.post', id=post.id))
    form.body.data = post.body
    return render_template('edit_post.html', form=form,id=post.id,Message=Message)


@main.route('/follow/<username>')
@login_required
@permission_required(Permission.FOLLOW)
def follow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash(u'用户不存在','warning')
        return redirect(url_for('.index'))
    if current_user.is_following(user):
        flash(u'你已经关注了此用户', 'info')
        return redirect(url_for('.user', username=username))
    current_user.follow(user)
    flash(u'关注 %s 成功.' % username, 'success')
    return redirect(url_for('.user', username=username))


@main.route('/unfollow/<username>')
@login_required
@permission_required(Permission.FOLLOW)
def unfollow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash(u'用户不存在', 'warning')
        return redirect(url_for('.index'))
    if not current_user.is_following(user):
        flash(u'你没有关注此用户','info')
        return redirect(url_for('.user', username=username))
    current_user.unfollow(user)
    flash(u'取消关注 %s 成功.' % username, 'info')
    return redirect(url_for('.user', username=username))


@main.route('/followers/<username>')
def followers(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash(u'用户不存在', 'warning')
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    pagination = user.followers.paginate(
        page, per_page=current_app.config['FLASKY_FOLLOWERS_PER_PAGE'],
        error_out=False)
    follows = [{'user': item.follower, 'timestamp': item.timestamp}
               for item in pagination.items]
    return render_template('followers.html', user=user, title=u"的关注者",
                           endpoint='.followers', pagination=pagination,
                           follows=follows,Message=Message)


@main.route('/followed-by/<username>')
def followed_by(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash(u'用户不存在', 'warning')
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    pagination = user.followed.paginate(
        page, per_page=current_app.config['FLASKY_FOLLOWERS_PER_PAGE'],
        error_out=False)
    follows = [{'user': item.followed, 'timestamp': item.timestamp}
               for item in pagination.items]
    return render_template('followers.html', user=user, title=u"关注的人",
                           endpoint='.followed_by', pagination=pagination,
                           follows=follows,Message=Message)


@main.route('/all')
@login_required
def show_all():
    resp = make_response(redirect(url_for('.index')))
    resp.set_cookie('show_followed', '', max_age=30*24*60*60)
    return resp


@main.route('/followed')
@login_required
def show_followed():
    resp = make_response(redirect(url_for('.index')))
    resp.set_cookie('show_followed', '1', max_age=30*24*60*60)
    return resp


@main.route('/moderate')
@login_required
@permission_required(Permission.MODERATE_COMMENTS)
def moderate():
    page = request.args.get('page', 1, type=int)
    pagination = Comment.query.order_by(Comment.timestamp.desc()).paginate(page, per_page=current_app.config['FLASKY_COMMENTS_PER_PAGE'],
                                                                           error_out=False)
    comments = pagination.items
    return render_template('moderate.html', comments=comments, pagination=pagination, page=page, ReComment=ReComment,Message=Message)


@main.route('/moderate/enable/<int:id>')
@login_required
@permission_required(Permission.MODERATE_COMMENTS)
def moderate_enable(id):
    comment = Comment.query.get_or_404(id)
    comment.disabled = False
    db.session.add(comment)
    db.session.commit()
    return redirect(url_for('.moderate',
                            page=request.args.get('page', 1, type=int)))


@main.route('/moderate/disable/<int:id>')
@login_required
@permission_required(Permission.MODERATE_COMMENTS)
def moderate_disable(id):
    comment = Comment.query.get_or_404(id)
    comment.disabled = True
    db.session.add(comment)
    db.session.commit()
    return redirect(url_for('.moderate',
                            page=request.args.get('page', 1, type=int)))


@main.route('/moderate/enable_re/<int:id>')
@login_required
@permission_required(Permission.MODERATE_COMMENTS)
def moderate_enablere(id):
    recomment = ReComment.query.get_or_404(id)
    recomment.disabled = False
    db.session.add(recomment)
    db.session.commit()
    return redirect(url_for('.moderate',
                            page=request.args.get('page', 1, type=int)))


@main.route('/moderate/disable_re/<int:id>')
@login_required
@permission_required(Permission.MODERATE_COMMENTS)
def moderate_disablere(id):
    recomment = ReComment.query.get_or_404(id)
    recomment.disabled = True
    db.session.add(recomment)
    db.session.commit()
    return redirect(url_for('.moderate',
                            page=request.args.get('page', 1, type=int)))

@main.route('/tag/<int:id>')
def tag(id):
    tag = Category.query.get_or_404(id)
    page = request.args.get('page', 1, type=int)
    query = tag.posts
    pagination = query.order_by(Post.timestamp.desc()).paginate(page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
                                                                     error_out=False)
    posts = pagination.items
    return render_template('tag.html',posts=posts,pagination=pagination,tag=tag,Category=Category,Message=Message)

def gen_rnd_filename():
    filename_prefix = datetime.now().strftime('%Y%m%d%H%M%S')
    return '%s%s' % (filename_prefix, str(random.randrange(1000, 10000)))
@main.route('/ckupload/', methods=['POST', 'OPTIONS'])
def ckupload():
    """CKEditor file upload"""
    error = ''
    url = ''
    callback = request.args.get("CKEditorFuncNum")
    if request.method == 'POST' and 'upload' in request.files:
        fileobj = request.files['upload']
        fname, fext = os.path.splitext(fileobj.filename)
        rnd_name = '%s%s' % (gen_rnd_filename(), fext)
        u = UploadToQiniu(fileobj)  
        ret, inf = u.upload()
        key = ret['key']
        url = u.domian_name+'/'+key
    else:
        error = 'post error'
    res = """<script type="text/javascript">
  window.parent.CKEDITOR.tools.callFunction(%s, '%s', '%s');
</script>""" % (callback, url, error)
    response = make_response(res)
    response.headers["Content-Type"] = "text/html"
    return response


@main.route('/se_message/<int:id>', methods=['GET', 'POST'])
@login_required
def se_message(id):
    contector = User.query.get_or_404(id)
    if contector == current_user:
        flash(u'不能给自己发送私信','danger')
        return redirect(url_for('.index'))
    l = []
    messgs = Message.query.filter_by(author_id=current_user.id).order_by(Message.timestamp.desc()).all()+Message.query.filter_by(sendto_id=current_user.id).order_by(Message.timestamp.desc()).all()
    for i in messgs:
        l.append(i.id)
    l.sort()
    fmessgs = []
    for i in l:
        fmessgs.append(Message.query.get(i))
    
    messageds = Message.query.filter_by(author_id=contector.id,sendto_id=current_user.id).order_by(Message.timestamp.asc()).all()
    unreadmessages = []
    for i in messageds:
        if not i.confirmed:
            unreadmessages.append(i)

    for i in messageds:
        i.confirmed = True
        db.session.add(i)
    form = MessageForm()
    if form.submit.data and form.validate_on_submit():
        msg = Message(body=form.body.data,author=current_user._get_current_object(),sendto=contector,confirmed=False)
        db.session.add(msg)
        db.session.commit()
        return redirect(url_for('.se_message', id=contector.id)+"#contectorform")
    return render_template('se_message.html',form=form,contector=contector,User=User,fmessgs=fmessgs, unreadmessages=unreadmessages,Message=Message)

@main.route('/message/<int:id>', methods=['GET', 'POST'])
@login_required
def message(id):
    user = User.query.get_or_404(id)
    if user != current_user:
        abort(403)
    l = []
    messgs = Message.query.filter_by(author_id=current_user.id).order_by(Message.timestamp.desc()).all()+Message.query.filter_by(sendto_id=current_user.id).order_by(Message.timestamp.desc()).all()
    for i in messgs:
        l.append(i.id)
    l.sort(reverse=True)
    fmessgs = []
    for i in l:
        fmessgs.append(Message.query.get(i))
    contectors = []
    for i in fmessgs:
        if i.author_id == current_user.id:
            if i.sendto.id not in contectors:
                contectors.append(i.sendto_id)
        else:
            if i.author.id not in contectors:
                contectors.append(i.author_id)
    return render_template('message.html',contectors=contectors,User=User,Message=Message)

@main.route('/testmsg/<int:id>')
def testmsg(id):
    unread = Message.query.filter_by(sendto_id=current_user.id,author_id=id,confirmed=False).order_by(Message.timestamp.asc()).first()
    if unread:
        unread.confirmed = True
        db.session.add(unread)
        db.session.commit()
        msgtime = unread.timestamp+timedelta(hours=8)
        msgtime = msgtime.strftime('%Y-%m-%d, %H:%M')
        return jsonify(result=unread.body,t=msgtime)
    
    return jsonify()
