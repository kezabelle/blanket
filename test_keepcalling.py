# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from blanket import keepcalling

def test_only_data():
    def myfunc():
        return {'status': 'OK'}
    assert keepcalling(myfunc) == {'status': 'OK'}


def test_one_level():
    def myfunc():
        def myfunc_child():
            return {'status': 'child'}
        return myfunc_child
    assert keepcalling(myfunc) == {'status': 'child'}


def test_many_level():
    def myfunc():
        def myfunc_child():
            def myfunc_grandchild():
                def myfunc_great_grandchild():
                    return {'status': 'great_grandchild'}
                return myfunc_great_grandchild
            return myfunc_grandchild
        return myfunc_child
    assert keepcalling(myfunc) == {'status': 'great_grandchild'}


def test_with_kwargs():
    def myfunc_child(a):
        return {'result': a}
    def myfunc(**kwargs):
        return myfunc_child
    assert keepcalling(myfunc, a='yay') == {'result': 'yay'}
