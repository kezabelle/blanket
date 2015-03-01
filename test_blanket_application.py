# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from wsgiref.util import setup_testing_defaults
from blanket import Blanket
from blanket import ViewConfig
from blanket import JSON
from blanket import BlanketValueError
from blanket import NoRouteFound
import pytest


def _ok_response(request):
    return {'yay': 1}


def _exception_handler(exception, request):
    return 'silenced {cls!r}, value: {val!s}'.format(cls=exception.__class__,
                                                     val=exception)


def _exception_raiser(request):
    raise BlanketValueError('test')


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
    app.add(path='/', handler=view)
    environ = {}
    setup_testing_defaults(environ)
    result = app.get_response(environ=environ)
    assert result.body == '{\n    "yay": 1\n}'


def test_unlikely_call_stack_get():
    app = Blanket()
    app.add(path='/', handler=_convoluted_response)
    environ = {}
    setup_testing_defaults(environ)
    result = app.get_response(environ=environ)
    assert result.body == {'called': 'get'}


def test_unlikely_call_stack_post():
    app = Blanket()
    app.add(path='/', handler=_convoluted_response)
    environ = {'REQUEST_METHOD': 'POST'}
    setup_testing_defaults(environ)
    result = app.get_response(environ=environ)
    assert result.body == {'called': 'post'}


def test_exception_causes_redirection_to_error_router():
    app = Blanket()
    app.add(path='/', handler=_exception_raiser)
    app.add(exception_class=ValueError, handler=_exception_handler)
    environ = {}
    setup_testing_defaults(environ)
    result = app.get_response(environ=environ)
    assert result.body == ("silenced <class 'blanket.BlanketValueError'>, "
                           "value: test")

def test_exception_during_request_creation():
    """
    Looks like webob.Request will happily build without a valid wsgi environ,
    so the PATH_INFO yields into NoRouteFound, which is in my code.
    :return:
    """
    app = Blanket()
    app.add(path='/', handler=_exception_raiser)
    app.add(exception_class=ValueError, handler=_exception_handler)
    with pytest.raises(NoRouteFound):
        app.get_response(environ={})


def test_add_path():
    app = Blanket()
    app.add(path='/', handler=_ok_response)


def test_add_exception():
    app = Blanket()
    app.add(exception_class=StandardError, handler=_ok_response)


def test_add_exception_and_path():
    app = Blanket()
    with pytest.raises(BlanketValueError):
        app.add(path='/', exception_class=StandardError, handler=_ok_response)


def test_add_handler_without_exception_or_path():
    app = Blanket()
    with pytest.raises(BlanketValueError):
        app.add(handler=_ok_response)
