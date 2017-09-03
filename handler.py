#!/usr/bin/env python
# -*- coding: utf-8 -*-

from tornado.web import RequestHandler
from tornado.websocket import WebSocketHandler
from tornado.web import escape
from tornado.gen import coroutine, Task
from models import User, Message, Session, Channel, ChannelUser
from redis_repository import ChannelRepository, UserRepository, \
    SessionRepository, MessageRepository, ChannelUserRepository
from common_exception import CommonException
from settings import db_settings
import tornadoredis


def authenticated_async(method):
    @coroutine
    def wrapper(self, *args, **kwargs):
        self._auto_finish = False
        self.current_user = yield Task(self.get_current_user_async)
        if not self.current_user:
            self.redirect('/login')
        else:
            result = method(self, *args, **kwargs)
            if result is not None:
                yield result

    return wrapper


class BaseHandler(RequestHandler):
    @coroutine
    def get_current_user_async(self):
        session_key = self.get_secure_cookie('session', max_age_days=1)
        if not session_key:
            return None
        db_connection = self.get_db_connection()
        session_key = session_key.decode('utf-8')
        session_repo = SessionRepository(db_connection)
        session = yield session_repo.filter({'key': session_key})
        if not session:
            yield self.release_db_connection(db_connection)
            return None

        user_id = session.user
        user_repo = UserRepository(db_connection)
        user = yield user_repo.get_one(user_id)
        session.user = user
        yield self.release_db_connection(db_connection)
        return user

    def write_json_response(self, json):
        self.write(escape.json_encode(json))
        self.finish()

    def get_db_connection(self):
        return tornadoredis.Client(connection_pool=self.application.connection_pool, **db_settings)

    @coroutine
    def release_db_connection(self, db_connection):
        yield Task(db_connection.disconnect)


class ChannelHandler(BaseHandler):
    @authenticated_async
    @coroutine
    def get(self, *args, **kwargs):
        channel_id = kwargs.get('channel')
        if channel_id:
            yield self.get_one_channel(channel_id)
        else:
            yield self.get_all_channels()

    @authenticated_async
    @coroutine
    def post(self, *args, **kwargs):
        db_connection = self.get_db_connection()
        already_joined = True
        channel_repo = ChannelRepository(db_connection)
        channel_name = self.get_argument('channel')
        channel = yield channel_repo.filter({'name': channel_name})
        if not channel:
            channel = Channel(name=channel_name)
            yield channel_repo.save(channel)
        channel_user_repo = ChannelUserRepository(db_connection)
        channel_user = yield channel_user_repo.filter({'user': self.current_user, 'channel': channel})
        if not channel_user:
            already_joined = False
            channel_user = ChannelUser(channel=channel, user=self.current_user, admin=True)
            yield channel_user_repo.save(channel_user)
            message_text = '{} has subscribed to the channel'.format(self.current_user.name)
            message = Message(channel=channel, text=message_text)
            message_repo = MessageRepository(db_connection)
            yield message_repo.save(message)
            yield message_repo.publish_message(message)
        yield self.release_db_connection(db_connection)
        self.write_json_response({'status': True,
                                  'channel': {
                                      'name': channel.name,
                                      'id': channel.id,
                                      'already_joined': already_joined,
                                  }})

    @authenticated_async
    @coroutine
    def delete(self, *args, **kwargs):
        channel_id = kwargs.get('channel')
        if not channel_id:
            return None
        db_connection = self.get_db_connection()
        channel_repo = ChannelRepository(db_connection)
        channel = yield channel_repo.get_one(channel_id)
        if not channel:
            yield self.release_db_connection(db_connection)
            return None
        channel_user_repo = ChannelUserRepository(db_connection)
        channel_user = yield channel_user_repo.filter({'channel': channel,
                                                       'user': self.current_user})
        yield channel_user_repo.delete(channel_user)
        message_text = '{} has unsubscribed from the channel'.format(self.current_user.name)
        message = Message(channel=channel, text=message_text)
        message_repo = MessageRepository(db_connection)
        yield message_repo.save(message)
        yield message_repo.publish_message(message)
        yield self.release_db_connection(db_connection)
        self.write_json_response({'status': True})

    @coroutine
    def get_all_channels(self):
        db_connection = self.get_db_connection()
        channel_user_repo = ChannelUserRepository(db_connection)
        channel_user = yield channel_user_repo.filter({'user': self.current_user})
        channel_repo = ChannelRepository(db_connection)
        channels = yield channel_repo.get_many([cu.channel for cu in channel_user])
        yield self.release_db_connection(db_connection)
        self.write_json_response({
            'channels': [{
                'id': c.id,
                'name': c.name,
            }
                for c in channels]
        })

    @coroutine
    def get_one_channel(self, channel_id):
        db_connection = self.get_db_connection()
        channel_repo = ChannelRepository(db_connection)
        channel = yield channel_repo.get_one(channel_id)
        channel_user_repo = ChannelUserRepository(db_connection)
        channel_user = yield channel_user_repo.filter({'channel': channel, 'user': self.current_user})
        if not channel_user:
            yield self.release_db_connection(db_connection)
            self.send_error(reason='Channel unavailable')
            return

        message_repo = MessageRepository(db_connection)
        messages = yield message_repo.filter({'channel': channel})
        user_repo = UserRepository(db_connection)
        users = yield user_repo.get_many(set([m.user for m in messages if m.user]))
        users_dict = {u.id: u for u in users if u}
        yield self.release_db_connection(db_connection)
        for message in messages:
            message.user = users_dict.get(message.user)
        messages = sorted(messages, key=lambda x: x.timestamp)
        self.write_json_response({
            'messages': [m.get_dict() for m in messages],
            'channel': channel.id
        })


class ChatHandler(BaseHandler):
    @authenticated_async
    def get(self, *args, **kwargs):
        self.render('index.html')


class LoginHandler(BaseHandler):
    def get(self):
        self.render('login.html')

    @coroutine
    def post(self, *args, **kwargs):
        db_connection = self.get_db_connection()
        login, password = self.get_login_password(*args, **kwargs)
        user_repo = UserRepository(db_connection)
        user = yield user_repo.filter({'name': login})
        if not user:
            self.render('login.html')
            return
        if not user.verify_password(password):
            self.render('login.html')
            return
        session = Session(user=user)
        self.set_secure_cookie('session', session.key, expires_days=1)
        session_repo = SessionRepository(db_connection)
        yield session_repo.save(session)
        yield self.release_db_connection(db_connection)
        self.redirect('/')

    def get_login_password(self, *args, **kwargs):
        login = self.get_argument('login')
        password = self.get_argument('password')
        return login, password


class LogoutHandler(BaseHandler):
    @authenticated_async
    @coroutine
    def get(self):
        session_key = self.get_secure_cookie('session', max_age_days=1)
        if not session_key:
            return None
        session_key = session_key.decode('utf-8')
        db_connection = self.get_db_connection()
        session_repo = SessionRepository(db_connection)
        session = yield session_repo.filter({'key': session_key})
        if not session:
            yield self.release_db_connection(db_connection)
            return None
        yield session_repo.delete(session)
        yield self.release_db_connection(db_connection)
        self.clear_cookie('session')
        self.redirect('/')


class SignUpHandler(BaseHandler):
    def get(self):
        self.render('sign_up.html')

    @coroutine
    def post(self, *args, **kwargs):
        login, password = self.get_login_password()
        db_connection = self.get_db_connection()
        user_repo = UserRepository(db_connection)
        user = User(name=login, password=User.new_password(password))
        try:
            yield user_repo.save(user)
        except CommonException:
            self.render('sign_up.html')
            return
        if not user:
            yield self.release_db_connection(db_connection)
            self.render('sign_up.html')
            return
        session = Session(user=user)
        self.set_secure_cookie('session', session.key)
        session_repo = SessionRepository(db_connection)
        yield session_repo.save(session)
        yield self.release_db_connection(db_connection)
        self.redirect('/')

    def get_login_password(self):
        login = self.get_argument('login')
        password = self.get_argument('password')
        return login, password


class WebSocketChannelHandler(BaseHandler, WebSocketHandler):
    def __init__(self, application, request, **kwargs):
        super(WebSocketChannelHandler, self).__init__(application, request, **kwargs)
        self.channel = None
        self.user = None
        self.subscribed = False
        self.subscribe_connection = self.get_db_connection()

    @authenticated_async
    @coroutine
    def open(self, *args, **kwargs):
        self.user = self.current_user
        if not self.user:
            self.close(reason='Unknown user')
            return
        db_connection = self.get_db_connection()
        channel_id = kwargs.get('channel')
        channel_repo = ChannelRepository(db_connection)
        self.channel = yield channel_repo.get_one(channel_id)
        if not self.channel:
            yield self.release_db_connection(db_connection)
            self.close(reason='Channel does not exist')
            return
        channel_user_repo = ChannelUserRepository(db_connection)
        channel_user = yield channel_user_repo.filter({'channel': self.channel, 'user': self.user})
        if not channel_user:
            yield self.release_db_connection(db_connection)
            self.close(reason='Channel unavailable')
            return

        channel_name = 'sub:channel:{}'.format(self.channel.id)
        yield Task(self.subscribe_connection.subscribe, channel_name)
        self.subscribed = True
        yield self.release_db_connection(db_connection)
        self.subscribe_connection.listen(callback=self.on_messages_published)

    @coroutine
    def on_message(self, message):
        decoded_message = escape.json_decode(message)
        text = decoded_message.get('message')
        if not text:
            self.send_error(reason='Empty text')
            return
        db_connection = self.get_db_connection()
        message = Message(user=self.user, channel=self.channel, text=text)
        message_repo = MessageRepository(db_connection)
        yield message_repo.save(message)
        yield message_repo.publish_message(message)
        yield self.release_db_connection(db_connection)

    @coroutine
    def on_close(self):
        if self.subscribed:
            channel_name = 'sub:channel:{}'.format(self.channel.id)
            yield Task(self.subscribe_connection.unsubscribe, channel_name)
            self.subscribed = False
            yield self.release_db_connection(self.subscribe_connection)

    @coroutine
    def on_messages_published(self, message):
        if message.kind == 'message':
            self.write_message(message.body)
