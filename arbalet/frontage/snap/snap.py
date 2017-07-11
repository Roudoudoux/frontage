#!/usr/bin/env python
"""
    Arbalet Frontage

    Copyright 2015 Yoan Mollard - Arbalet project - http://github.com/arbalet-project
    License: GPL version 3 http://www.gnu.org/licenses/gpl.html
"""

from flask import Flask
from flask import request
from flask_cors import CORS
from flask import render_template
from flask import request, Response
from functools import wraps

from ..controller import Frontage
from webbrowser import open
from numpy.random import randint
from threading import RLock
import sys
import signal

from tornado.wsgi import WSGIContainer
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
import tornado.gen

import petname
from time import time
from time import sleep
import datetime
import logging
import socket



def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    return username == 'admin' and password == './arbalet'


def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


class SnapServer(object):
    def __init__(self, port, hardware=True, simulator=True):
        self.flask = Flask(__name__)
        self.frontage = Frontage(33460, hardware, simulator)  # Blocking until the hardware client connects
        logging.basicConfig(level=logging.DEBUG)
        self.current_auth_nick = ""
        self.nicknames = {}
        self.lock = RLock()
        CORS(self.flask)
        self.port = int(port)
        self.route()
    
    def signal_handler(self, signal, frame):
        self.frontage.close()
        sys.exit(0)

    def route(self):
        self.flask.route('/admin', methods=['GET', 'POST'])(self.render_admin_page)
        #self.flask.route('/set_pixel_rgb', methods=['POST'])(self.set_pixel_rgb)
        self.flask.route('/set_rgb_matrix', methods=['POST'])(self.set_rgb_matrix)
        self.flask.route('/is_authorized/<nickname>', methods=['GET'])(self.is_authorized)
        self.flask.route('/authorize', methods=['POST'])(self.authorize)
        self.flask.route('/get_nickname', methods=['GET'])(self.get_nickname)

    def check_nicknames_validity(self):
        with self.lock:
            temp_dict = {}
            for k, v in self.nicknames.iteritems():
                if time() - v < 20:
                    temp_dict[k] = v
            self.nicknames = temp_dict

    @requires_auth
    def render_admin_page(self):
        res = render_template('admin.html', nicknames=self.nicknames.keys(), authorized_nick=self.current_auth_nick)
        return res

    @requires_auth
    def authorize(self):
        with self.lock:
            self.current_auth_nick = request.get_data()
            self.erase_all()
        return ''

    @staticmethod
    def scale(v):
        return min(255., max(0., int(v)))

    def set_rgb_matrix(self):
        try:
            data = request.get_data().split(':')
            with self.lock:
                if data.pop(0) == self.current_auth_nick:
                    nb_rows = 4
                    nb_cols = 19
                    r = 0
                    c = 0
                    while data:
                        red = data.pop(0)
                        green = data.pop(0)
                        blue = data.pop(0)
                        self.frontage[r, c] = map(self.scale, [red, green, blue])
                        if c < nb_cols - 1:
                            c += 1
                        else:
                            c = 0
                            r += 1
        except Exception:
            raise
            sys.exc_clear()
        return ''  

    def erase_all(self):
        self.frontage.set_all(0, 0, 0)
        return ''

    #def set_pixel_rgb(self):
    #    try:
    #        data = request.get_data().split(':')
    #        with self.lock:
    #            if data[-1] == self.current_auth_nick:
    #                self.frontage[int(data[1])-1, int(data[0])-1] = map(self.scale, data[2:-1])
    #    except Exception:
    #        sys.exc_clear()
    #    return ''

    def is_authorized(self, nickname):
        with self.lock:
            self.nicknames[nickname] = time()
        # update user table
        self.check_nicknames_validity()
        return str(nickname == self.current_auth_nick)

    def get_nickname(self):
        rand_id = petname.generate()
        with self.lock:
            while rand_id in self.nicknames.keys():
                rand_id = petname.generate()
            self.nicknames[rand_id] = time()
        return rand_id

    def run(self):
        # open('http://snap.berkeley.edu/run')
        signal.signal(signal.SIGINT, self.signal_handler)
        try:
            loop = IOLoop()
            http_server = HTTPServer(WSGIContainer(self.flask))
            http_server.listen(self.port)
            loop.start()
            
        except socket.error as serr:
            # Re raise the socket error if not "[Errno 98] Address already in use"
            if serr.errno != errno.EADDRINUSE:
                raise serr
            else:
                logger.warning("""The webserver port {} is already used.
The Snap Server is maybe already run or another software use this port.""".format(self.port))

