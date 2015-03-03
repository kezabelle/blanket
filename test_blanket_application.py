# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from wsgiref.util import setup_testing_defaults
from blanket import Blanket
# from blanket import ViewConfig
from blanket import JSON
from blanket import BlanketValueError
from blanket import NoErrorHandler
import pytest


def _ok_response(request, randomvalue):
    return {'yay': int(randomvalue)}


def _exception_handler(exception, request):
    return 'silenced {cls!r}, value: {val!s}'.format(cls=exception.__class__,
                                                     val=exception)


def _exception_raiser(request):
    raise BlanketValueError('test')


def _convoluted_post(request, test):
    return {'called': 'post', 'kwarg': test}


class _ConvolutedResponse(object):
    def __init__(self, request, test):
        pass

    def __call__(self, request, test):
        return getattr(self, request.method.lower())

    def get(self, request, test):
        return {'called': 'get', 'kwarg': test}

    def post(self, request, test):
        return _convoluted_post


def _convoluted_response(request, test):
    return _ConvolutedResponse
#
#
# def test_get_ok_response():
#     app = Blanket()
#     view = ViewConfig(views=[_ok_response], outputs=[JSON])
#     app.add(path='{randomvalue!d}', handler=view)
#     environ = {'PATH_INFO': '/14'}
#     setup_testing_defaults(environ)
#     result = app.get_response(environ=environ)
#     assert result.body == '{\n    "yay": 14\n}'


def test_unlikely_call_stack_get():
    """
    This tests the complex nature of keepcalling through the stack.
    specifically, goes through:
    - a function
    - a class __init__
    - a class __call__
    - a class method
    - a class method which yields another function.
    """
    app = Blanket()
    app.add(path='/{test!x}/', handler=_convoluted_response, outputs=[JSON])
    environ = {'PATH_INFO': '/FFCCFF/'}
    setup_testing_defaults(environ)
    result = app.get_response(environ=environ)
    assert result.body == {'called': 'get', 'kwarg': 'FFCCFF'}


def test_unlikely_call_stack_post():
    app = Blanket()
    app.add(path='/{test!x}/', handler=_convoluted_response, outputs=[JSON])
    environ = {'REQUEST_METHOD': 'POST', 'PATH_INFO': '/CCFFCC/'}
    setup_testing_defaults(environ)
    result = app.get_response(environ=environ)
    assert result.body == {'called': 'post', 'kwarg': 'CCFFCC'}


def test_exception_causes_redirection_to_error_router():
    app = Blanket()
    app.add(path='/', handler=_exception_raiser, outputs=[JSON])
    app.add(exception_class=ValueError, handler=_exception_handler,
            outputs=[JSON])
    environ = {}
    setup_testing_defaults(environ)
    result = app.get_response(environ=environ)
    assert result.body == ("silenced <class 'blanket.BlanketValueError'>, "
                           "value: test")


def test_exception_during_request_creation():
    """
    Looks like webob.Request will happily build without a valid wsgi environ,
    so the PATH_INFO yields into NoRouteHandler, which is in my code.
    :return:
    """
    app = Blanket()
    app.add(path='/', handler=_exception_raiser, outputs=[JSON])
    app.add(exception_class=ValueError, handler=_exception_handler,
            outputs=[JSON])
    environ = {'PATH_INFO': '/not/the/root/route/'}
    setup_testing_defaults(environ)
    with pytest.raises(NoErrorHandler):
        app.get_response(environ=environ)


def test_add_path():
    app = Blanket()
    app.add(path='/', handler=_ok_response, outputs=[JSON])


def test_add_exception():
    app = Blanket()
    app.add(exception_class=StandardError, handler=_ok_response, outputs=[JSON])


def test_add_exception_and_path():
    app = Blanket()
    with pytest.raises(BlanketValueError):
        app.add(path='/', exception_class=StandardError, handler=_ok_response,
                outputs=[JSON])


def test_add_handler_without_exception_or_path():
    app = Blanket()
    with pytest.raises(BlanketValueError):
        app.add(handler=_ok_response, outputs=[JSON])
