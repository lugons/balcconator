#!/usr/bin/env python
# -*- coding: utf-8 -*-

import config

from flask import Flask, render_template, make_response, request, g, session, flash, redirect, url_for, abort
app = Flask(__name__)

#from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from flaskext.sqlalchemy import SQLAlchemy
db = SQLAlchemy(app)

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
    gender = db.Column(db.Enum('male', 'female', 'unspecified'))
    email = db.Column(db.String(120), unique=True)
    registration_date = db.Column(db.DateTime)
    groups = db.relationship('Group', secondary=groupmembers, backref=db.backref('groups', lazy='dynamic'))
                                
    def __init__(self, username, password, firstname, lastname, displayname, gender, email):
        self.username = username
        self.password = sha1(password).hexdigest()
        self.firstname = firstname
        self.lastname = lastname
        self.displayname = displayname
        self.gender = gender
        self.email = email
        self.registration_date = datetime.utcnow()

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


def check_permissions(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # based on the url - request.path: /item/edit, /item/view, /item/list, ... 
        # based on a function argument: @check_permissions(needuser='foo', needgroup='bar')
        username = session.get('username', None)
        if not username:
            flash('The access to that page is restricted. You need to be logged in as a user with proper permissions.', 'error')
            return redirect(url_for('login'))

        return f(*args, **kwargs)
    return decorated_function


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


@app.route('/people/<username>/')
def person(username):
    g.person = Person.query.filter_by(username=username).first()
    return render_template('person.html')


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
        person = Person.query.filter_by(username=request.form['username'], password=sha1(request.form['password']).hexdigest()).first()
        if person is None:
            flash('Invalid username or password. Please try again.', 'error')
            return render_template('login.html')

        else:
            # valid login
            session['username'] = person.username
            flash('Login successful.')
            return redirect(url_for('index'))

    else:
        return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('Logged out. Thank you for your visit.')
    return redirect(url_for('index'))


@app.route('/register')
def register():
    if session.get('username', None):
        flash('You are already logged in. Please log out before registering a new account.')
        return redirect(url_for('index'))

    return render_template('register.html')


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
    return render_template('401.html'), 404


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
