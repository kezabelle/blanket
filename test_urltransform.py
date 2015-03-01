# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from blanket import URLTransformRegistry
from blanket import RoutePattern


def test_repr():
    urls = URLTransformRegistry()
    expected = ("<blanket.URLTransformRegistry "
                "registry=<blanket.TransformRegistry prefix_keys='{' "
                "suffix_keys='!day}', '!d}', '!f}', '!month}', '!slug}', "
                "'!s}', '!uuid}', '!x}', '!year}'>>")
    assert repr(urls) == expected


def test_contains():
    urls = URLTransformRegistry()
    assert '{' in urls.registry


def test_length():
    urls = URLTransformRegistry()
    assert len(urls.registry) == 10


def test_plain():
    urls = URLTransformRegistry()
    result = urls.make('a/b/c')
    assert result.raw == 'a/b/c'
    assert result.regex.pattern == '^/a/b/c$'
    assert isinstance(result, RoutePattern)
    assert result.regex.match('/a/b/c')
    assert not result.regex.match('/a/b/d')


def test_complex():
    urls = URLTransformRegistry()
    result = urls.make('{hex!s}/{id!s}/{uuid!uuid}/{num!d}/{decimal!f}/'
                       '{username!slug}')
    expected = ('^/(?P<hex>.+?)/(?P<id>.+?)/(?P<uuid>[0-9a-f]{8}-[0-9a-f]{4}-'
                '[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{32})/'
                '(?P<num>[0-9]+?)/(?P<decimal>[0-9]+\.[0-9]+?)/(?P<username>[a-z0-9_-]+?)$')
    assert result.regex.pattern == expected
    assert result.regex.match('/af/???/8bbd4c5b-a040-43d1-8b99-8a19e9b29feb/4/4.2/hello_world-')


def test_dateformat():
    urls = URLTransformRegistry()
    result = urls.make('year/{yyyy!year}/month/{mm!month}/day/{dd!day}')
    assert result.regex.match('/year/2000/month/01/day/02')
    assert result.regex.match('/year/1000/month/12/day/15')
    assert not result.regex.match('/year/999/month/12/day/15') # bad year length
    assert not result.regex.match('/year/1999/month/13/day/01') # bad month
    assert not result.regex.match('/year/1999/month/00/day/01') # bad month
    assert not result.regex.match('/year/1999/month/12/day/32') # bad day (max)
    assert not result.regex.match('/year/1999/month/12/day/00') # bad day (min)
