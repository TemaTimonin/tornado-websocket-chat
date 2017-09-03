#!/usr/bin/env python
# -*- coding: utf-8 -*-

from tornado.gen import Task, coroutine
from tornado import escape


class BaseMapper(object):
    name = None

    def __init__(self, connection):
        super(BaseMapper, self).__init__()
        self.connection = connection

    @coroutine
    def acquire_lock(self, name):
        lock_name = 'lock:{}:{}'.format(self.name, name)
        lock = self.connection.lock(lock_name, lock_ttl=1)
        if not lock:
            return None

        result = yield Task(lock.acquire, blocking=True)
        if not result:
            return None
        return lock

    @coroutine
    def release_lock(self, lock):
        yield Task(lock.release)

    @coroutine
    def get_new_id(self):
        index_key = '{}:id'.format(self.name)
        _id = yield Task(self.connection.incr, index_key)
        return _id

    @coroutine
    def save(self, values):
        _id = values.get('id')
        model_key = '{}:{}'.format(self.name, _id)
        self.connection.hmset(model_key, values)

    @coroutine
    def delete(self, model):
        model_key = '{}:{}'.format(self.name, model.id)
        yield self.connection.delete(model_key)

    @coroutine
    def get_one(self, _id):
        if _id is None:
            return None
        model_key = '{0}:{1}'.format(self.name, _id)
        result = yield Task(self.connection.hgetall, model_key)
        return result

    @coroutine
    def get_many(self, ids):
        if not ids:
            return []
        pipeline = self.connection.pipeline(True)
        for _id in ids:
            key_name = '{}:{}'.format(self.name, _id)
            pipeline.hgetall(key_name)
        data = yield Task(pipeline.execute)
        return data

    @coroutine
    def set_index_value(self, _id, indexed_value):
        name_key = '{}s'.format(self.name)
        yield self.connection.hset(name_key, indexed_value, _id)

    @coroutine
    def get_index_value(self, indexed_value):
        name_key = '{}s'.format(self.name)
        _id = yield Task(self.connection.hget, name_key, indexed_value)
        return _id

    @coroutine
    def delete_index(self, indexed_value):
        index_key = '{}s:'.format(self.name)
        yield self.connection.hdel(index_key, indexed_value)

    @coroutine
    def save_foreign_keys_relations(self, model, fk_from, fk_to):
        model_foreign_key = '{}:{}:{}s'.format(fk_from, getattr(model, fk_from).id, self.name)
        yield Task(self.connection.sadd, model_foreign_key, model.id)

    @coroutine
    def delete_foreign_keys_relation(self, model, fk_from, fk_to):
        key = '{}:{}:{}s'.format(fk_from, getattr(model, fk_from).id,  fk_to)
        yield Task(self.connection.srem, key, model.id)


class UserMapper(BaseMapper):
    name = 'user'


class SessionMapper(BaseMapper):
    name = 'session'


class ChannelMapper(BaseMapper):
    name = 'channel'


class MessageMapper(BaseMapper):
    name = 'message'

    @coroutine
    def get_by_channel(self, channel):
        messages_key = '{0}:{1}:{2}s'.format('channel', channel.id, self.name)
        message_ids = yield Task(self.connection.smembers, messages_key)
        messages = yield self.get_many(message_ids)
        return messages

    @coroutine
    def publish(self, message):
        channel_name = 'sub:channel:{}'.format(message.channel.id)
        yield Task(self.connection.publish, channel=channel_name,
                   message=escape.json_encode(message.get_dict()))


class ChannelUserMapper(BaseMapper):
    name = 'channel_user'

    @coroutine
    def get_by_user_and_channel(self, user, channel):
        store_name = '{}:{}:{}:{}'.format('channel', channel.id, 'user', user.id)
        lock_name = 'lock:{}'.format(store_name)
        lock = self.connection.lock(lock_name, lock_ttl=1)
        if not lock:
            return None

        result = yield Task(lock.acquire)
        if not result:
            return None

        keys = ['{}:{}:{}s'.format('user', user.id, 'channel'),
                '{}:{}:{}s'.format('channel', channel.id, 'user')]
        pipeline = self.connection.pipeline(True)
        pipeline.zinterstore(store_name, keys)
        pipeline.zrange(store_name, 0, -1, with_scores=False)
        status, ids = yield Task(pipeline.execute)
        yield Task(lock.release)
        if not ids:
            return None
        _id = ids[0]
        data = yield self.get_one(_id)
        return data

    @coroutine
    def get_by_user(self, user):
        key = '{}:{}:{}s'.format('user', user.id, 'channel')
        ids = yield Task(self.connection.zrange, key, 0, -1, with_scores=False)
        data = yield self.get_many(ids)
        return data

    @coroutine
    def get_by_channel(self, channel):
        key = '{}:{}:{}s'.format('channel', channel.id, 'user')
        ids = yield Task(self.connection.zrange, key, 0, -1, with_scores=False)
        data = yield self.get_many(ids)
        return data

    @coroutine
    def delete_foreign_keys_relation(self, model, fk_from, fk_to):
        key = '{}:{}:{}s'.format(fk_from, getattr(model, fk_from).id,  fk_to)
        yield Task(self.connection.zrem, key, model.id)

    @coroutine
    def save_foreign_keys_relations(self, model, fk_from, fk_to):
        model_foreign_key = '{}:{}:{}s'.format(fk_from, getattr(model, fk_from).id, fk_to)
        status = yield Task(self.connection.zadd, model_foreign_key, getattr(model, fk_to).id, model.id)
        return status

    @coroutine
    def delete_foreign_keys_relation(self, model, fk_from, fk_to):
        key = '{}:{}:{}s'.format(fk_from, getattr(model, fk_from).id,  fk_to)
        yield Task(self.connection.zrem, key, model.id)
