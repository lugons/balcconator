#!/usr/bin/env python
# -*- coding: utf-8 -*-

import config

from flask import Flask, render_template, make_response, request, g, session, flash, redirect, url_for
app = Flask(__name__)

from sqlalchemy.dialects import postgresql
from flaskext.sqlalchemy import SQLAlchemy
db = SQLAlchemy(app)

from functools import wraps
from datetime import datetime
from hashlib import sha1
#from recaptcha.client import captcha


##
# database models
groupmembers = db.Table('groupmembers',
    db.Column('groupname', db.String(40), db.ForeignKey('group.groupname')),
    db.Column('username', db.String(40), db.ForeignKey('person.username'))
)


class Person(db.Model):
    username = db.Column(db.String(40), primary_key=True)
    password = db.Column(db.String(40))
    fullname = db.Column(db.String(80), unique=True)
    email = db.Column(db.String(120), unique=True)
    registration_date = db.Column(db.DateTime)
    groups = db.relationship('Group', secondary=groupmembers, backref=db.backref('groups', lazy='dynamic'))
                                
    def __init__(self, username, password, fullname, email):
        self.username = username
        self.password = sha1(password).hexdigest()
        self.fullname = fullname
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


##
# decorator functions
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not 'username' in session.keys():
            flash('You need to be logged in to access that page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def check_permissions(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # request.path
        # based on the url, e.g.: /item/edit, /item/view, /item/list, ...
#        if not 'username' in session.keys():
#            flash('You do not have the required permissions to access that page.', 'error')
#            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


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
@check_permissions
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


@app.route('/login', methods=['POST', 'GET'])
def login():
    error = None
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
    flash('Logged out. Thank you for your visit.')
    session.pop('username', None)
    return redirect(url_for('index'))


@app.route('/register')
def register():
    if session['username']:
        flash('You are already logged in. Please log out before registering a new account.')
        return redirect(url_for('index'))

    return render_template('todo.html')


@app.route('/admin/')
def admin():
    return render_template('admin.html')


@app.route('/admin/groups/')
def admin_groups():
    g.groups = Group.query.all()
    return render_template('admin_groups.html')


# this shouldn't be available in production, it's here to add some test data
@app.route('/admin/initdb')
def admin_initdb():
    db.drop_all()
    db.create_all()
    admin = Person('admin', 'adm1n', 'Administrator', 'admin@localhost')
    john = Person('john', 'john', 'John Doe', 'john@localhost')
    jane = Person('jane', 'jane', 'Jane Doe', 'jane@localhost')
    admins = Group('admins', 'Administrators', 'admins@localhost')
    lecturers = Group('lecturers', 'Lecturers', 'lecturers@localhost')

    admin.groups.append(admins)
    john.groups.append(lecturers)
    jane.groups.append(lecturers)
    db.session.add(admin)
    db.session.add(john)
    db.session.add(jane)
    db.session.add(admins)
    db.session.commit()

    flash('Database (re)initialized.')
    return redirect(url_for('index'))


# TODO: remove when finished testing/styling in css
@app.route('/flash')
def flash_test():
    flash('This is an error message', 'error')
    flash('This is a message without a category')
    return render_template('index.html')


@app.route('/debug')
def debug():
    flash(dir(db))
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
