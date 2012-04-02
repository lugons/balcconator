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

    admin = Person('admin', 'adm1n', 'Administrator', 'admin@localhost')
    john = Person('john', 'john', 'John Doe', 'john@localhost')
    jane = Person('jane', 'jane', 'Jane Doe', 'jane@localhost')
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
