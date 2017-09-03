#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os


settings = {
    'cookie_secret': 'A2HTBv9PSQ6sFe0GwKD4V4JxUyARC08FvDcwDkSNXsA=',
    'template_path': os.path.join(os.path.dirname(__file__), 'templates'),
    'static_path': os.path.join(os.path.dirname(__file__), 'static'),
    'login_url': '/login',
    'xsrf_cookies': True,
    'debug': True,
    'autoreload': True,
    'server_traceback': True,
}

db_settings = {
    'host': '127.0.0.1',
    'port': 6379,
}

db_pool_settings = {
    'max_connections': 100,
    'wait_for_available': True
}
