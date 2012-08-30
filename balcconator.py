#!/usr/bin/env python
# -*- coding: utf-8 -*-

import config, os

from werkzeug.utils import secure_filename
from flask import Flask, render_template, make_response, request, g, session, flash, redirect, url_for, abort, send_from_directory, safe_join
app = Flask(__name__)

#from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from flaskext.sqlalchemy import SQLAlchemy
db = SQLAlchemy(app)

from flaskext.mail import Mail, Message
mail = Mail(app)

from functools import wraps
from datetime import datetime
from hashlib import sha1
import qrencode, StringIO
#from recaptcha.client import captcha

from textile import textile
from cgi import escape


##
# database models
groupmembers = db.Table('groupmembers',
    db.Column('groupname', db.String(40), db.ForeignKey('group.groupname')),
    db.Column('username', db.String(40), db.ForeignKey('person.username'))
)


class Person(db.Model):
    username = db.Column(db.String(40), primary_key=True)
    password = db.Column(db.String(40))
    firstname = db.Column(db.String(40))
    lastname = db.Column(db.String(40))
    displayname = db.Column(db.String(80))
    gender = db.Column(db.Enum('male', 'female', 'unspecified', name='gender'))
    email = db.Column(db.String(120))
    registration_date = db.Column(db.DateTime)
    confirmation_code = db.Column(db.String(40), nullable=True)
    groups = db.relationship('Group', secondary=groupmembers, backref=db.backref('groups', lazy='dynamic'))
    events = db.relationship('Event', backref='events', lazy='dynamic')

    permission_news = db.Column(db.Boolean)
    permission_reviewer = db.Column(db.Boolean)
    permission_venue = db.Column(db.Boolean)

    def __init__(self, username, password='', email='', firstname='', lastname='', displayname='', gender='unspecified', confirmation_code=None, permission_news=False, permission_reviewer=False, permission_venue=False):
        self.username = username
        self.password = sha1(password).hexdigest()
        self.email = email
        self.firstname = firstname
        self.lastname = lastname
        if not displayname:
            self.displayname = username
        else:
            self.displayname = displayname
        self.gender = gender
        self.registration_date = datetime.utcnow()
        self.confirmation_code = confirmation_code

        self.permission_news = permission_news
        self.permission_reviewer = permission_reviewer
        self.permission_venue = permission_venue

    def __repr__(self):
        return '<Person %r>' % self.username


class Group(db.Model):
    groupname = db.Column(db.String(40), primary_key=True)
    displayname = db.Column(db.String(80))
    email = db.Column(db.String(120), unique=True)
    registration_date = db.Column(db.DateTime)
    members = db.relationship('Person', secondary=groupmembers, backref=db.backref('members', lazy='dynamic'))

    def __init__(self, groupname, displayname, email):
        self.groupname = groupname
        self.displayname = displayname
        self.email = email
        self.registration_date = datetime.utcnow()

    def __repr__(self):
        return '<Group %r>' % self.groupname


class News(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(80))
    text = db.Column(db.Text)
    date = db.Column(db.DateTime)

    def __init__(self, title, text):
        self.title = title
        self.text = text # CLOB
        self.date = datetime.utcnow()

    def __repr__(self):
        return '<News %r>' % self.id


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    person = db.Column(db.String(40), db.ForeignKey('person.username'))
    title = db.Column(db.String(80))
    text = db.Column(db.Text)
    start = db.Column(db.DateTime)
    end = db.Column(db.DateTime)
    venue = db.Column(db.String(40), db.ForeignKey('venue.id'))

    def __init__(self, person, title, text, start, end, venue):
        self.person = person
        self.title = title
        self.text = text
        self.start = start
        self.end = end
        self.venue = venue

    def __repr__(self):
        return '<Event %r>' % self.id


class Venue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(80))
    description = db.Column(db.Text)
    address = db.Column(db.Text)
    events = db.relationship('Event', backref='venue_events', lazy='dynamic')

    def __init__(self, title, description, address):
        self.title = title
        self.description = description
        self.address = address

    def __repr__(self):
        return '<Venue %r>' % self.id


##
# decorator functions
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        username = session.get('username', None)
        if not username:
            flash('You need to be logged in to access that page.', 'error')
            abort(401)
            return redirect(url_for('login'))

        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        username = session.get('username', None)
        if not (username == 'admin'):
            flash('You need to be logged in as an administrator to access that page.', 'error')
            abort(401)
            return redirect(url_for('login'))

        return f(*args, **kwargs)
    return decorated_function


@app.before_request
def check_csrf():
    if not session.get('csrf'):
        session['csrf'] = sha1(os.urandom(400)).hexdigest()

    if request.method == 'POST':
        if not request.form['csrf'] == session.get('csrf'):
            abort(400)


@app.before_request
def fetch_permissions():
    username = session.get('username', None)
    if not username:
        g.permission_news = False
        g.permission_reviewer = False
        g.permission_venue = False

    else:
        user = Person.query.filter_by(username=username).first()
        g.permission_news = user.permission_news
        g.permission_reviewer = user.permission_reviewer
        g.permission_venue = user.permission_venue


@app.template_filter()
def reverse(s):
    return s[::-1]


@app.template_filter(name="textile")
def textilefilter(s):
    return textile(escape(s))


##
# views
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/people/')
def people():
    g.people = Person.query.all()
    return render_template('people.html')


@app.route('/people/<username>/', methods=['POST', 'GET'])
def person(username):
    if request.method == 'POST':
        if request.form['action'] == 'documentupload':
            if not username == session.get('username', None):
                flash('The access to that page is restricted. You need to be logged in as a user with proper permissions.', 'error')
                return redirect(url_for('login'))

            else:
                file = request.files['file']
                filename = secure_filename(file.filename)
                path = safe_join(safe_join(app.config['DOCUMENTS_LOCATION'], 'pending'), username)
                if not os.path.exists(path):
                    os.makedirs(path)
                file.save(safe_join(path, filename))
                flash('Document uploaded. Now it needs to be approved by a reviewer.')

        elif request.form['action'] == 'editpersonaldetails':
            if not username == session.get('username', None):
                flash('The access to that page is restricted. You need to be logged in as a user with proper permissions.', 'error')
                return redirect(url_for('login'))

            else:
                person = Person.query.filter_by(username=username).first()
                person.firstname = request.form['firstname']
                person.lastname = request.form['lastname']
                person.displayname = request.form['displayname']
                person.gender = request.form['gender']

                try:
                    db.session.add(person)
                    db.session.commit()
                    flash('Personal data updated.')

                except IntegrityError as err:
                    flash(err.message, 'error')
                    db.session.rollback()

                except SQLAlchemyError:
                    db.session.rollback()
                    flash('Something went wrong.')

        elif request.form['action'] == 'changepassword':
            if not username == session.get('username', None):
                flash('The access to that page is restricted. You need to be logged in as a user with proper permissions.', 'error')
                return redirect(url_for('login'))

            else:
                if request.form['new_password'] != request.form['confirm_new_password']:
                    flash('Repeated password is not the same as the new password. Please try again.', 'error')

                else:
                    person = Person.query.filter_by(username=username, password=sha1(request.form['old_password']).hexdigest()).first()
                    if person is None:
                        flash('Current password does not match. Please try again.', 'error')

                    else:
                        person.password = sha1(request.form['new_password']).hexdigest()
                        try:
                            db.session.add(person)
                            db.session.commit()
                            flash('Password updated.')

                        except IntegrityError as err:
                            flash(err.message, 'error')
                            db.session.rollback()

                        except SQLAlchemyError:
                            db.session.rollback()
                            flash('Something went wrong.')

        elif request.form['action'] == 'publish':
            if not g.permission_reviewer:
                flash('The access to that page is restricted. You need to be logged in as a user with proper permissions.', 'error')
                return redirect(url_for('login'))

            else:
                username = request.form['username']
                filename = secure_filename(request.form['document'])
                src_path = safe_join(safe_join(app.config['DOCUMENTS_LOCATION'], 'pending'), username)
                src = safe_join(src_path, filename)
                dst_path = safe_join(safe_join(app.config['DOCUMENTS_LOCATION'], 'public'), username)
                dst = safe_join(dst_path, filename)
                if not os.path.exists(dst_path):
                    os.makedirs(dst_path)

                if not os.path.exists(src):
                    flash('Document not found. Is it hiding in a closet, or are you meesing with the system?', error)

                else:
                    os.rename(src, dst)
                    flash('Document published.')

    try:
        g.documents_public = os.listdir(safe_join(safe_join(app.config['DOCUMENTS_LOCATION'], 'public'), username))
    except:
        g.documents_public = []

    try:
        g.documents_pending = os.listdir(safe_join(safe_join(app.config['DOCUMENTS_LOCATION'], 'pending'), username))
    except:
        g.documents_pending = []

    g.person = Person.query.filter_by(username=username).first()
    return render_template('person.html')


@app.route('/people/<username>/vcard')
def vcard(username):
    g.person = Person.query.filter_by(username=username).first()
    response = make_response(render_template('vcard.vcf'))
    response.headers['Content-Type'] = 'text/vcard'
    response.headers['Content-Disposition'] = 'attachment;filename="' + username + '.vcf"'
    return response


@app.route('/people/<username>/<filename>')
def document_public(username, filename):
    path = safe_join(safe_join(app.config['DOCUMENTS_LOCATION'], 'public'), username)
    return send_from_directory(path, filename)


@app.route('/people/<username>/pending/<filename>')
def document_pending(username, filename):
    if username == session.get('username', None) or g.permission_reviewer:
        path = safe_join(safe_join(app.config['DOCUMENTS_LOCATION'], 'pending'), username)
        return send_from_directory(path, filename)

    abort(401)


@app.route('/groups/')
def groups():
    g.groups = Group.query.all()
    return render_template('groups.html')


@app.route('/groups/<groupname>/')
def group(groupname):
    g.group = Group.query.filter_by(groupname=groupname).first()
    return render_template('group.html')


@app.route('/news/')
def news():
    g.news = News.query.order_by(News.date.desc()).all()
    return render_template('news.html')


@app.route('/news/<int:news_id>')
def news_item(news_id):
    g.news_item = News.query.filter_by(id=news_id).first()
    return render_template('news_item.html')


@app.route('/news/<int:news_id>/edit', methods=['POST', 'GET'])
def news_edit(news_id):
    if not g.permission_news:
        abort(401)

    news_item = News.query.filter_by(id=news_id).first()
    if request.method == 'POST':
        news_item.title = request.form['title']
        news_item.text = request.form['text']

        try:
            db.session.add(news_item)
            db.session.commit()
            flash('News updated.')

        except IntegrityError as err:
            flash(err.message, 'error')
            db.session.rollback()

        except SQLAlchemyError:
            db.session.rollback()
            flash('Something went wrong.')

        return redirect(url_for('news_item', news_id=news_item.id))

    g.news_item = news_item
    return render_template('news_edit.html')


@app.route('/news/add', methods=['POST', 'GET'])
def news_add():
    if not g.permission_news:
        abort(401)

    if request.method == 'POST':
        news_item = News(
            request.form['title'],
            request.form['text'],
        )

        try:
            db.session.add(news_item)
            db.session.commit()
            flash('News added.')

        except IntegrityError as err:
            flash(err.message, 'error')
            db.session.rollback()

        except SQLAlchemyError:
            db.session.rollback()
            flash('Something went wrong.')

        return redirect(url_for('news_item', news_id=news_item.id))

    return render_template('news_add.html')


@app.route('/schedule/')
def schedule():
    g.events = Event.query.order_by(Event.start.asc()).all()
    return render_template('schedule.html')


@app.route('/schedule/<int:day>')
def schedule_day(day):
    g.day = day
    return render_template('schedule.html')


@app.route('/papers/')
def papers():
    return render_template('papers.html')


@app.route('/sponsors/')
def sponsors():
    return render_template('sponsors.html')


@app.route('/contact')
def contact():
    return render_template('contact.html')


@app.route('/tickets')
def tickets():
    return render_template('tickets.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/venue/')
def venue():
    g.venues = Venue.query.all()
    return render_template('venue.html')


@app.route('/venue/<int:venue_id>')
def venue_individual(venue_id):
    g.venue = Venue.query.filter_by(id=venue_id).first()
    return render_template('venue_individual.html')


@app.route('/venue/<int:venue_id>/edit', methods=['POST', 'GET'])
def venue_edit(venue_id):
    if not g.permission_venue:
        abort(401)

    return render_template('venue_edit.html')


@app.route('/venue/add', methods=['POST', 'GET'])
def venue_add():
    if not g.permission_venue:
        abort(401)

    return render_template('venue_add.html')


@app.route('/friends')
def friends():
    return render_template('friends.html')


@app.route('/login', methods=['POST', 'GET'])
def login():
    if session.get('username', None):
        flash('You are already logged in. Log out first if you want to change to a different user.')
        return redirect(url_for('index'))

    if request.method == 'POST':
        person = Person.query.filter_by(username=request.form['username'], password=sha1(request.form['password']).hexdigest(), confirmation_code=None).first()
        if person is None:
            flash('Invalid username or password. Please try again.', 'error')
            g.referrer = request.form['referrer']
            return render_template('login.html')

        else:
            # valid login
            session['username'] = person.username
            flash('Login successful.')
            return redirect(request.form['referrer'] or url_for('person', username=person.username))

    else:
        g.referrer = request.referrer or ''
        return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out. Thank you for your visit.')
    return redirect(request.referrer or url_for('index'))


@app.route('/register', methods=['POST', 'GET'])
def register():
    if session.get('username', None):
        flash('You are already logged in. Please log out before registering a new account.')
        return redirect(url_for('index'))

    if request.method == 'POST':
        if request.form['password'] != request.form['confirm_password']:
            flash('The passwords do not match', 'error')

        elif Person.query.filter_by(username=request.form['username']).first() != None:
            flash('The username is already taken, please choose a different one', 'error')

        elif request.form['username'] != secure_filename(request.form['username']):
            flash('The username contains characters that are not allowed, please choose a different one', 'error')

        else:
            confirmation_code=sha1(os.urandom(400)).hexdigest()
            username=request.form['username']
            email=request.form['email']
            person = Person(
                username=username,
                password=request.form['password'],
                email=email,
                confirmation_code=confirmation_code
            )

            try:
                db.session.add(person)
                db.session.commit()
                message="Hello, %s\n\nSomeone has registered for BalCCon with this e-mail address.\nIf it was not done by you, just ignore this message.\nOtherwise, please click the following link to confirm your registration:\n%s\n\nHave a nice day,\nBalCCon administration team" % (username, url_for('register_confirm', _external=True, username=username, code=confirmation_code))
                msg = Message(subject="BalCCon registration",recipients=[email],body=message)
                mail.send(msg)
                flash('Confirmation e-mail sent.')
                return redirect(url_for('register_confirm', username=username))

            except IntegrityError as err:
                flash(err.message, 'error')
                db.session.rollback()

            except SQLAlchemyError:
                db.session.rollback()
                flash('Something went wrong.')

    return render_template('register.html')

@app.route('/register/confirm')
def register_confirm():
    code = username = ''
    if 'code' in request.args.keys():
        code = request.args['code']
    if 'username' in request.args.keys():
        username = request.args['username']

    if code and username:
        try:
            person = Person.query.filter_by(username=username, confirmation_code=code).first()
            person.confirmation_code=None
            db.session.add(person)
            db.session.commit()
            flash('Registration confirmed')
            session['username'] = person.username
            return redirect(url_for('person', username=person.username))

        except IntegrityError as err:
            flash(err.message, 'error')
            db.session.rollback()

        except SQLAlchemyError:
            db.session.rollback()
            flash('Something went wrong.')

    g.username = username
    g.code = code
    return render_template('register_confirm.html')

@app.route('/admin/')
@admin_required
def admin():
    return render_template('admin.html')


@app.route('/admin/groups/', methods=['POST', 'GET'])
@admin_required
def admin_groups():
    if request.method == 'POST':
        if request.form['action'] == 'add':
            group = Group(request.form['groupname'], request.form['displayname'], request.form['email'])
            db.session.add(group)
            db.session.commit()
            flash('Group added.')

        elif request.form['action'] == 'delete':
            group = Group.query.filter_by(groupname=request.form['groupname']).first()
            db.session.delete(group)
            db.session.commit()
            flash('Group deleted.')


    g.groups = Group.query.all()
    return render_template('admin_groups.html')


@app.route('/admin/people/', methods=['POST', 'GET'])
@admin_required
def admin_people():
    if request.method == 'POST':
        if request.form['action'] == 'add':
            person = Person(
                request.form['username'],
                request.form['password'],
                request.form['firstname'],
                request.form['lastname'],
                request.form['displayname'],
                request.form['gender'],
                request.form['email'],
            )

            try:
                db.session.add(person)
                db.session.commit()
                flash('Person added.')

            except IntegrityError as err:
                flash(err.message, 'error')
                db.session.rollback()

            except SQLAlchemyError:
                db.session.rollback()
                flash('Something went wrong.')

        elif request.form['action'] == 'delete':
            person = Person.query.filter_by(groupname=request.form['username']).first()
            db.session.delete(person)
            db.session.commit()
            flash('Person deleted.')

    g.people = Person.query.all()
    return render_template('admin_people.html')


@app.route('/admin/review', methods=['POST', 'GET'])
def admin_review():
    if not g.permission_reviewer:
        abort(401)

    if request.method == 'POST':
        username = request.form['username']
        filename = secure_filename(request.form['document'])
        src_path = safe_join(safe_join(app.config['DOCUMENTS_LOCATION'], 'pending'), username)
        src = safe_join(src_path, filename)
        dst_path = safe_join(safe_join(app.config['DOCUMENTS_LOCATION'], 'public'), username)
        dst = safe_join(dst_path, filename)
        if not os.path.exists(dst_path):
            os.makedirs(dst_path)

        if not os.path.exists(src):
            flash('Document not found. Is it hiding in a closet, or are you meesing with the system?', error)

        else:
            os.rename(src, dst)
            flash('Document published.')

    g.documents = []
    users = os.listdir(safe_join(app.config['DOCUMENTS_LOCATION'], 'pending'))
    for user in users:
        user_documents = os.listdir(safe_join(safe_join(app.config['DOCUMENTS_LOCATION'], 'pending'), user))
        for user_document in user_documents:
            g.documents.append((user, user_document))

    return render_template('admin_review.html')


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(401)
def unauthorized(e):
    return render_template('401.html'), 401


@app.errorhandler(400)
def unauthorized(e):
    return render_template('400.html'), 400


@app.route('/qr', defaults={'path': ''})
@app.route('/<path:path>/qr')
def qr(path):
    text = request.url[:-3]

    image = qrencode.encode_scaled(text, 120)[2]
    image = image.convert('RGB')

    recoloured = []
    for pixel in image.getdata():
        if pixel == (255, 255, 255):
            pixel = (0, 192, 0)
        recoloured.append(pixel)
    image.putdata(recoloured)

    output = StringIO.StringIO()
    format = 'PNG'
    image.save(output, format)
    contents = output.getvalue()
    output.close()

    response = make_response(contents)
    response.headers['Content-Type'] = 'image/png'
    return response


@app.route('/textile2html', methods=['POST', 'GET'])
def textile2html():
    if request.method == 'POST':
        return textilefilter(request.form['data'])

    else:
        flash('This page needs POST data to process.', 'error')
        return render_template('index.html')


# TODO: remove when finished testing/styling in css
@app.route('/flash')
def flash_test():
    flash('This is an error message', 'error')
    flash('This is a message without a category')
    return render_template('index.html')


app.config.from_object('config')
app.config.from_envvar('BALCCONATOR_SETTINGS', silent=True)

if not app.debug:
    import logging
    from logging import FileHandler
    file_handler = FileHandler(app.config['LOG_FILE'])
    file_handler.setLevel(logging.WARNING)
    app.logger.addHandler(file_handler)


##
# run the standalone server
if __name__ == '__main__':
    app.run()
