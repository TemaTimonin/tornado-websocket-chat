#!/usr/bin/env python
# -*- coding: utf-8 -*-

from common_exception import CommonException
from datetime import datetime, timedelta
from os import urandom
from hashlib import sha256
import bcrypt
from calendar import timegm
from time import time


class BaseModel(object):
    def __init__(self, id):
        super(BaseModel, self).__init__()
        self.id = id

    def __eq__(self, other):
        return self.id == other.id


class User(BaseModel):
    def __init__(self, id=None, name=None, password=None,
                 admin=False, session=None, channels=None):
        super(User, self).__init__(id)
        self.name = name
        self.password = password
        self.admin = admin
        self.session = session
        self.channels = channels if channels else []

    def verify_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password.encode('utf-8'))

    @staticmethod
    def new_password(password):
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


class Channel(BaseModel):
    def __init__(self, id=None, name=None, users=None, messages=None):
        super(Channel, self).__init__(id)
        self.name = name
        self.users = users if users else []
        self.messages = messages if messages else []

    def add_user(self, user):
        if user in self.users:
            raise CommonException('User already in chat')
        self.users.append(user)

    def delete_user(self, user):
        del self.users[user]

    def get_messages(self):
        return sorted(self.messages, key=lambda x: x.timestamp)


class Message(BaseModel):
    def __init__(self, id=None, user=None, channel=None, text=None, timestamp=None):
        super(Message, self).__init__(id)
        self.user = user
        self.channel = channel
        self.text = text
        self.timestamp = timestamp if timestamp \
            else datetime_to_timestamp(datetime.utcnow())

    def get_dict(self):
        return {
            'timestamp': self.timestamp,
            'text': self.text,
            'user': self.user.name if self.user else None,
            'id': self.id,
        }


class Session(BaseModel):
    def __init__(self, id=None, user=None, key=None, expires=None, timezone=0):
        super(Session, self).__init__(id)
        self.user = user
        self.key = key if key else self.generate_session()
        self.expires = expires if expires \
            else datetime_to_timestamp(datetime.utcnow() + timedelta(days=1))
        self.timezone = timezone

    def generate_session(self):
        parts = [
            str(urandom(128)),
            str(time()),
            str(self.user.id)
        ]
        result = sha256('_'.join(parts).encode('utf-8')).hexdigest()
        return result


class ChannelUser(BaseModel):
    def __init__(self, id=None, channel=None, user=None,
                 admin=False, subscribed=None):
        super(ChannelUser, self).__init__(id)
        self.channel = channel
        self.user = user
        self.admin = admin
        self.subscribed = subscribed if subscribed \
            else datetime_to_timestamp(datetime.utcnow())


def datetime_to_timestamp(dt):
    return timegm(dt.timetuple())
