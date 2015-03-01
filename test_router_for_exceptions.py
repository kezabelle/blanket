# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from blanket import ErrorRouter
from blanket import RouteExistsAlready
from blanket import NoRouteFound
import pytest


def test_suppresses_exceptions():
    router = ErrorRouter()
    def swallow_error(exception, request):
        return {'swallowed': exception.__class__.__name__}
    router.add(exception_class=TypeError, handler=swallow_error)
    router.add(exception_class=ValueError, handler=swallow_error)
    result = router(exception=TypeError("Hello!"), request=None)
    assert result == {'swallowed': 'TypeError'}
    result2 = router(exception=ValueError(4), request=None)
    assert result2 == {'swallowed': 'ValueError'}

def test_error_on_duplicates():
    router = ErrorRouter()
    router.add(exception_class=TypeError, handler=lambda x: x)
    with pytest.raises(RouteExistsAlready):
            router.add(exception_class=TypeError, handler=lambda x: x)


def test_find_no_matching_path():
    router = ErrorRouter()
    def swallow_error(exception, request):
        return {'swallowed': exception.__class__.__name__}
    router.add(exception_class=TypeError, handler=swallow_error)
    router.add(exception_class=ValueError, handler=swallow_error)
    with pytest.raises(NoRouteFound):
        router(exception=KeyError('test'))
