# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from wsgiref.util import setup_testing_defaults
from blanket import Blanket
from blanket import ViewConfig
from blanket import JSON

def _ok_response(request):
    return {'yay': 1}


def _convoluted_post(request, *args, **kwargs):
    return {'called': 'post'}


class _ConvolutedResponse(object):
    def __init__(self, request, *args, **kwargs):
        pass

    def __call__(self, request, *args, **kwargs):
        return getattr(self, request.method.lower())

    def get(self, request, *args, **kwargs):
        return {'called': 'get'}

    def post(self, request, *args, **kwargs):
        return _convoluted_post


def _convoluted_response(request, *args, **kwargs):
    return _ConvolutedResponse


def test_get_ok_response():
    app = Blanket()
    view = ViewConfig(views=[_ok_response], outputs=[JSON])
    app.router.add(path='/', handler=view)
    environ = {}
    setup_testing_defaults(environ)
    result = app.get_response(environ=environ)
    assert result.body == '{\n    "yay": 1\n}'


def test_unlikely_call_stack_get():
    app = Blanket()
    app.router.add(path='/', handler=_convoluted_response)
    environ = {}
    setup_testing_defaults(environ)
    result = app.get_response(environ=environ)
    assert result.body == {'called': 'get'}


def test_unlikely_call_stack_post():
    app = Blanket()
    app.router.add(path='/', handler=_convoluted_response)
    environ = {'REQUEST_METHOD': 'POST'}
    setup_testing_defaults(environ)
    result = app.get_response(environ=environ)
    assert result.body == {'called': 'post'}
