#!/usr/bin/env python
# -*- coding: utf-8 -*-

from handler import ChatHandler, ChannelHandler, LoginHandler, \
    LogoutHandler, WebSocketChannelHandler, SignUpHandler
from tornado.web import StaticFileHandler
from settings import settings

urls = [
    (r"/", ChatHandler),
    (r"/static/(.*)", StaticFileHandler, {'path': settings.get('static_path')}),
    (r"/channel", ChannelHandler),
    (r"/channel/(?P<channel>\w+)", ChannelHandler),
    (r"/login", LoginHandler),
    (r"/logout", LogoutHandler),
    (r"/sign_up", SignUpHandler),
    (r"/chatsocket/(?P<channel>\w+)", WebSocketChannelHandler),
]
