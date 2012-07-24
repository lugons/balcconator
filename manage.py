#!/usr/bin/env python
# -*- coding: utf-8 -*-

from balcconator import app
from flaskext.script import Manager
manager = Manager(app)


@manager.command
def hello():
    print "hello"


@manager.command
def initdb():
    from balcconator import db, Person, Group
    db.drop_all()
    db.create_all()

    admins = Group('admins', 'Administrators', 'admins@localhost')
    lecturers = Group('lecturers', 'Lecturers', 'lecturers@localhost')
    db.session.add(admins)
    db.session.add(lecturers)

    # username, password, email, firstname, lastname, displayname, gender
    admin = Person('admin', 'adm1n', 'admin@localhost', '', '', 'Administrator', 'unspecified')
    john = Person('john', 'john', 'john@localhost', 'John', 'Doe', 'John Doe', 'male')
    jane = Person('jane', 'jane', 'jane@localhost', 'Jane', 'Doe', 'Jane Doe', 'female')
    admin.groups.append(admins)
    john.groups.append(lecturers)
    john.groups.append(admins)
    jane.groups.append(lecturers)

    db.session.add(admin)
    db.session.add(john)
    db.session.add(jane)

    db.session.commit()


if __name__ == "__main__":
    manager.run()
