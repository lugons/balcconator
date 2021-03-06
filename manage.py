#!/usr/bin/env python
# -*- coding: utf-8 -*-

from balcconator import app
from flaskext.script import Manager
manager = Manager(app)

permissions = ['news', 'reviewer', 'venue', 'schedule']

@manager.command
def grant(username, permission):
    if not permission in permissions:
        print 'Unknown permission.'
        return

    from balcconator import db, Person
    person = Person.query.filter_by(username=username).first()

    if not person:
        print 'Username not found.'
        return

    setattr(person, 'permission_' + permission, True)
    db.session.add(person)
    db.session.commit()
    print 'Permission', permission, 'granted to', username


@manager.command
def ungrant(username, permission):
    if not permission in permissions:
        print 'Unknown permission.'
        return

    from balcconator import db, Person
    person = Person.query.filter_by(username=username).first()

    if not person:
        print 'Username not found.'
        return

    setattr(person, 'permission_' + permission, False)
    db.session.add(person)
    db.session.commit()
    print 'Permission', permission, 'removed from', username


@manager.command
def initdb():
    from balcconator import db, Person, Group, Event, Venue

    db.drop_all()
    db.create_all()


@manager.command
def add_example_data():
    from balcconator import db, Person, Group, Event, Venue

    admins = Group('admins', 'Administrators', 'admins@localhost')
    lecturers = Group('lecturers', 'Lecturers', 'lecturers@localhost')
    db.session.add(admins)
    db.session.add(lecturers)

    # username, password, email, firstname, lastname, displayname, gender
    admin = Person('admin', 'adm1n', 'admin@localhost', '', '', 'Administrator', 'unspecified', permission_news=True, permission_reviewer=True, permission_venue=True, permission_schedule=True)
    john = Person('john', 'john', 'john@localhost', 'John', 'Doe', 'John Doe', 'male')
    jane = Person('jane', 'jane', 'jane@localhost', 'Jane', 'Doe', 'Jane Doe', 'female')
    reviewer = Person('reviewer', 'reviewer', 'reviewer@localhost', '', '', 'Reviewer', 'unspecified', permission_reviewer=True)
    admin.groups.append(admins)
    john.groups.append(lecturers)
    john.groups.append(admins)
    jane.groups.append(lecturers)

    db.session.add(admin)
    db.session.add(john)
    db.session.add(jane)
    db.session.add(reviewer)

    db.session.commit()

    # title, description, address
    sala1 = Venue('Sala 1', 'Velika sala na 1. spratu', 'Ulica i broj')
    sala2 = Venue('Sala 2', 'Mala sala na 2. spratu', 'Ulica i broj')
    restoran = Venue('Restoran', 'Restoran u hotelu', u'Sunčani kej bb')
    db.session.add(sala1)
    db.session.add(sala2)
    db.session.add(restoran)
    db.session.commit()

    from datetime import datetime
    # person, title, text, start, end
    ev1 = Event('admin', 'Welcome Party', 'The opening ceremony of the conference', datetime(2013, 9, 1, 20, 0), datetime(2013, 9, 1, 23, 59), 3)
    db.session.add(ev1)
    db.session.commit()

    ev2 = Event('john', 'John 101', 'Foreword by John', datetime(2013, 9, 2, 10, 0), datetime(2013, 9, 2, 12, 59), 1)
    ev3 = Event('jane', 'Jane 101', 'Foreword by Jane', datetime(2013, 9, 2, 13, 0), datetime(2013, 9, 2, 13, 59), 2)
    ev4 = Event('john', 'John 102', 'Continuation by John', datetime(2013, 9, 2, 14, 0), datetime(2013, 9, 2, 14, 59), 1)
    db.session.add(ev2)
    db.session.add(ev3)
    db.session.add(ev4)
    db.session.commit()


if __name__ == "__main__":
    manager.run()
