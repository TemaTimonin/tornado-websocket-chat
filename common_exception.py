#!/usr/bin/env python
# -*- coding: utf-8 -*-


class CommonException(Exception):
    def __init__(self, message):
        super(CommonException, self).__init__(message)
