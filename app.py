#!/usr/bin/env python
# -*- coding: utf-8 -*-

from tornado.ioloop import IOLoop
from tornado.web import Application
from tornado.httpserver import HTTPServer
from tornado import options
from settings import settings, db_pool_settings
from url import urls
import tornadoredis
import time
import signal


options.define("port", default=8888, help="http server port", type=int)


class Chat(Application):
    def __init__(self):
        super(Chat, self).__init__(urls, **settings)
        self.connection_pool = tornadoredis.ConnectionPool(**db_pool_settings)


def make_safely_shutdown(server, timeout=5):
    io_loop = IOLoop.instance()

    def stop_handler(*args, **keywords):
        def shutdown():
            server.stop()
            deadline = time.time() + timeout

            def stop_loop():
                now = time.time()
                if now < deadline:
                    io_loop.add_timeout(now + 1, stop_loop)
                else:
                    io_loop.stop()
            stop_loop()
        io_loop.add_callback(shutdown)
    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)


if __name__ == "__main__":
    options.parse_command_line()
    app = Chat()
    server = HTTPServer(app)
    server.listen(options.options.port)
    make_safely_shutdown(server, timeout=1)
    IOLoop.current().start()
