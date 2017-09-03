#!/usr/bin/env python
# -*- coding: utf-8 -*-

from models import BaseModel, Session, User, Channel, ChannelUser, Message
from redis_mapper import BaseMapper, UserMapper, SessionMapper, ChannelMapper, MessageMapper, ChannelUserMapper
from common_exception import CommonException
from tornado.gen import coroutine


class BaseRepository(object):
    model_attributes = ('id', )
    model = BaseModel

    def __init__(self, connection):
        super(BaseRepository, self).__init__()
        self.mapper = BaseMapper(connection)

    @coroutine
    def get_one(self, _id):
        data = yield self.mapper.get_one(_id)
        return self._create_model(data)

    @coroutine
    def get_many(self, ids):
        data = yield self.mapper.get_many(ids)
        return [self._create_model(d) for d in data]

    @coroutine
    def filter(self, query):
        raise NotImplemented()

    @coroutine
    def delete(self, instance):
        yield self.mapper.delete(instance)

    @coroutine
    def save(self, instance):
        _id = yield self.mapper.get_new_id()
        if _id is None:
            raise CommonException('Save error')

        instance.id = _id
        values = self._get_model_attributes(instance)
        yield self.mapper.save(values)
        return instance

    def _get_model_attributes(self, instance):
        return {attr: getattr(instance, attr) for attr in self.model_attributes}

    def _create_model(self, data):
        if not data:
            return None
        return self.model(**data)


class UserRepository(BaseRepository):
    model_attributes = ('id', 'name', 'password', 'admin')
    model = User

    def __init__(self, connection):
        super(UserRepository, self).__init__(connection)
        self.mapper = UserMapper(connection)

    @coroutine
    def save(self, user):
        lock = yield self.mapper.acquire_lock(user.name)
        _id = yield self.mapper.get_index_value(user.name)
        if _id:
            raise CommonException('Already exist')

        _id = yield self.mapper.get_new_id()
        if _id is None:
            raise CommonException('Save error')

        yield self.mapper.set_index_value(_id, user.name)
        user.id = _id
        values = self._get_model_attributes(user)
        yield self.mapper.save(values)
        yield self.mapper.release_lock(lock)
        return user

    @coroutine
    def delete(self, user):
        yield self.mapper.delete(user)
        yield self.mapper.delete_index(user.name)

    @coroutine
    def filter(self, query):
        if 'name' in query:
            _id = yield self.mapper.get_index_value(query.get('name'))
            result = yield self.get_one(_id)
            return result
        return None


class SessionRepository(BaseRepository):
    model_attributes = ('id', 'key', 'user', 'expires', 'timezone')
    model = Session

    def __init__(self, connection):
        super(SessionRepository, self).__init__(connection)
        self.mapper = SessionMapper(connection)

    @coroutine
    def save(self, session):
        lock = yield self.mapper.acquire_lock(session.key)
        _id = yield self.mapper.get_index_value(session.key)
        if _id:
            raise CommonException('Already exist')

        _id = yield self.mapper.get_new_id()
        if _id is None:
            raise CommonException('Save error')

        yield self.mapper.set_index_value(_id, session.key)
        session.id = _id
        values = self._get_model_attributes(session)
        values['user'] = session.user.id
        yield self.mapper.save(values)
        yield self.mapper.release_lock(lock)
        return session

    @coroutine
    def filter(self, query):
        if 'key' in query:
            _id = yield self.mapper.get_index_value(query.get('key'))
            result = yield self.get_one(_id)
            return result
        return None

    @coroutine
    def delete(self, session):
        yield self.mapper.delete(session)
        yield self.mapper.delete_index(session.key)

    def _create_model(self, data):
        if not data:
            return None
        data['expires'] = int(data['expires'])
        return self.model(**data)

    def _get_model_attributes(self, message):
        result = {}
        for attr in self.model_attributes:
            result[attr] = getattr(message, attr)
            if attr == 'user':
                result[attr] = result[attr].id
        return result


class ChannelRepository(BaseRepository):
    model_attributes = ('id', 'name')
    model = Channel

    def __init__(self, connection):
        super(ChannelRepository, self).__init__(connection)
        self.mapper = ChannelMapper(connection)

    @coroutine
    def save(self, channel):
        lock = yield self.mapper.acquire_lock(channel.name)
        _id = yield self.mapper.get_index_value(channel.name)
        if _id:
            raise CommonException('Already exist')

        _id = yield self.mapper.get_new_id()
        if _id is None:
            raise CommonException('Save error')

        yield self.mapper.set_index_value(_id, channel.name)
        channel.id = _id
        values = self._get_model_attributes(channel)
        yield self.mapper.save(values)
        yield self.mapper.release_lock(lock)
        return channel

    @coroutine
    def filter(self, query):
        if 'name' in query:
            _id = yield self.mapper.get_index_value(query.get('name'))
            result = yield self.get_one(_id)
            return result
        return None

    @coroutine
    def delete(self, channel):
        yield self.mapper.delete(channel)
        yield self.mapper.delete_index(channel.name)


class MessageRepository(BaseRepository):
    model_attributes = ('id', 'text', 'channel', 'user', 'timestamp')
    model = Message

    def __init__(self, connection):
        super(MessageRepository, self).__init__(connection)
        self.mapper = MessageMapper(connection)

    @coroutine
    def save(self, message):
        message = yield super(MessageRepository, self).save(message)
        yield self.mapper.save_foreign_keys_relations(message, 'channel', 'user')
        if message.user:
            yield self.mapper.save_foreign_keys_relations(message, 'user', 'channel')
        return message

    @coroutine
    def filter(self, query):
        if 'channel' in query:
            channel = query['channel']
            data = yield self.mapper.get_by_channel(channel)
            return [self._create_model(d) for d in data]
        return None

    def _create_model(self, data):
        if data is None:
            return None
        data['timestamp'] = int(data['timestamp'])
        model = self.model(**data)
        return model

    @coroutine
    def publish_message(self, message):
        yield self.mapper.publish(message)

    def _get_model_attributes(self, message):
        result = {}
        for attr in self.model_attributes:
            result[attr] = getattr(message, attr)
            if attr == 'user':
                result[attr] = result[attr].id if result[attr] else None
            if attr == 'channel':
                result[attr] = result[attr].id
        return result


class ChannelUserRepository(BaseRepository):
    model_attributes = ('id', 'channel', 'user', 'subscribed', 'admin')
    model = ChannelUser

    def __init__(self, connection):
        super(ChannelUserRepository, self).__init__(connection)
        self.mapper = ChannelUserMapper(connection)

    @coroutine
    def save(self, channel_user):
        channel_user = yield super(ChannelUserRepository, self).save(channel_user)
        yield self.mapper.save_foreign_keys_relations(channel_user, 'channel', 'user')
        yield self.mapper.save_foreign_keys_relations(channel_user, 'user', 'channel')
        return channel_user

    @coroutine
    def filter(self, query):
        if 'user' in query and 'channel' in query:
            user = query['user']
            channel = query['channel']
            data = yield self.mapper.get_by_user_and_channel(user, channel)
            if not data:
                return None
            data['user'] = user
            data['channel'] = channel
            return self._create_model(data)
        elif 'user' in query:
            data = yield self.mapper.get_by_user(query['user'])
            return [self._create_model(d) for d in data]
        elif 'channel' in query:
            data = yield self.mapper.get_by_channel(query['channel'])
            return [self._create_model(d) for d in data]

        return None

    @coroutine
    def delete(self, model):
        yield self.mapper.delete_foreign_keys_relation(model, 'channel', 'user')
        yield self.mapper.delete_foreign_keys_relation(model, 'user', 'channel')
        yield super(ChannelUserRepository, self).delete(model)

    def _get_model_attributes(self, message):
        result = {}
        for attr in self.model_attributes:
            result[attr] = getattr(message, attr)
            if attr == 'user':
                result[attr] = result[attr].id
            if attr == 'channel':
                result[attr] = result[attr].id
        return result
