#!/usr/bin/env python
# -*- coding: utf-8 -*-

import config, os

from werkzeug.utils import secure_filename
from flask import Flask, render_template, make_response, request, g, session, flash, redirect, url_for, abort, send_from_directory
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
#from recaptcha.client import captcha

from textile import textile


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

    def __init__(self, username, password='', email='', firstname='', lastname='', displayname='', gender='unspecified', confirmation_code=None, permission_news=False, permission_reviewer=False):
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
    id = db.Column(db.String(40), primary_key=True)
    title = db.Column(db.String(80))
    text = db.Column(db.Text)
    address = db.Column(db.Text)
    events = db.relationship('Event', backref='venue_events', lazy='dynamic')

    def __init__(self, id, title, text, address):
        self.id = id
        self.title = title
        self.text = text
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
def fetch_permissions():
    username = session.get('username', None)
    if not username:
        g.permission_news = False
        g.permission_reviewer = False

    else:
        user = Person.query.filter_by(username=username).first()
        g.permission_news = user.permission_news
        g.permission_reviewer = user.permission_reviewer


@app.template_filter()
def reverse(s):
    return s[::-1]


@app.template_filter(name="textile")
def textilefilter(s):
    return textile(s)


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
        # allow POST only if the correct user is logged in
        if not username == session.get('username', None):
            flash('The access to that page is restricted. You need to be logged in as a user with proper permissions.', 'error')
            return redirect(url_for('login'))

        else:
            if request.form['action'] == 'documentupload':
                file = request.files['file']
                filename = secure_filename(file.filename)
                path = os.path.join(app.config['DOCUMENTS_LOCATION'], 'pending', username)
                if not os.path.exists(path):
                    os.makedirs(path)
                file.save(os.path.join(path, filename))
                flash('Document uploaded. Now it needs to be approved by a reviewer.')

    try:
        g.documents_public = os.listdir(os.path.join(app.config['DOCUMENTS_LOCATION'], 'public', username))
    except:
        g.documents_public = []

    try:
        g.documents_pending = os.listdir(os.path.join(app.config['DOCUMENTS_LOCATION'], 'pending', username))
    except:
        g.documents_pending = []

    g.person = Person.query.filter_by(username=username).first()
    return render_template('person.html')


@app.route('/people/<username>/<filename>')
def document_public(username, filename):
    path = os.path.join(app.config['DOCUMENTS_LOCATION'], 'public', username)
    return send_from_directory(path, filename)


@app.route('/people/<username>/pending/<filename>')
def document_pending(username, filename):
    if username == session.get('username', None) or g.permission_reviewer:
        path = os.path.join(app.config['DOCUMENTS_LOCATION'], 'pending', username)
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


@app.route('/venue')
def venue():
    g.venues = Venue.query.all()
    return render_template('venue.html')


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
    session.pop('username', None)
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
            print 'person:', person
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


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(401)
def unauthorized(e):
    return render_template('401.html'), 401


@app.route('/textile2html', methods=['POST', 'GET'])
def textile2html():
    if request.method == 'POST':
        return textile(request.form['data'])

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
