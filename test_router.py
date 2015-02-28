# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from blanket import Router
from blanket import RouteExistsAlready
from blanket import NoRouteFound
import pytest
from webob import Request


def _fake_handler(*args, **kwargs):
        return {'test': 'OK'}


def test_router_add():
    router = Router()
    router.add(path='test/{a!s}/', handler=_fake_handler)
    assert len(router.seen_routes) == 1
    assert router.seen_routes == frozenset(['test/{a!s}/'])


def test_router_add_duplicate():
    router = Router()
    router.add(path='test/{a!s}/', handler=_fake_handler)
    with pytest.raises(RouteExistsAlready):
            router.add(path='test/{a!s}/', handler=lambda x: x)


def test_router_repr():
    router = Router()
    router.add(path='test/{a!s}/', handler=_fake_handler)
    router.add(path='test2/{a!s}/', handler=_fake_handler)
    router.add(path='test3/{a!s}/', handler=_fake_handler)
    router.add(path='test4/{a!s}/', handler=_fake_handler)
    expected = ("<blanket.Router routes=[<blanket.Route pattern=<blanket."
                "RoutePattern raw='test/{a!s}/', regex='^/test/(?P<a>.+?)/$'>,"
                " handler=test_router._fake_handler>, <blanket.Route pattern="
                "<blanket.RoutePattern raw='test2/{a!s}/', regex='^/test2/"
                "(?P<a>.+?)/$'>, handler=test_router._fake_handler>, "
                "<blanket.Route pattern=<blanket.RoutePattern "
                "raw='test3/{a!s}/', regex='^/test3/(?P<a>.+?)/$'>, "
                "handler=test_router._fake_handler>], 1 remaining ...>")
    assert repr(router) == expected


def test_find_match():
    router = Router()
    router.add(path='test/{a!s}/', handler=_fake_handler)
    router.add(path='test2/{a!s}/', handler=_fake_handler)
    request = Request.blank('/test2/goose/')
    result = router(request=request)
    assert result == {'test': 'OK'}


def test_find_no_matching_path():
    router = Router()
    router.add(path='test/{a!s}/', handler=_fake_handler)
    router.add(path='test2/{a!s}/', handler=_fake_handler)
    request = Request.blank('/test2/')
    with pytest.raises(NoRouteFound):
        router(request=request)


def test_find_via_magicmethod_contains():
    router = Router()
    router.add(path='test/{a!s}/', handler=_fake_handler)
    router.add(path='/test2/{a!s}/', handler=_fake_handler)
    request = Request.blank('/test2/wee/')
    assert request.path in router
    assert '/test2/' not in router