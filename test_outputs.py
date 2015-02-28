# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from blanket import JSON
from blanket import mustache
from webob import Request


def test_json():
    request = Request.blank('/')
    assert JSON(request=request, context={
        'test': 1,
        'output': 2,
    }) == '{\n    "test": 1, \n    "output": 2\n}'


def test_mustache():
    context = {
        "template": """
            Hello {{name}}
            You have just won {{value}} dollars!
            {{#in_ca}}
            Well, {{taxed_value}} dollars, after taxes.
            {{/in_ca}}
        """,
        "name": "Chris",
        "value": 10000,
        "taxed_value": 10000 - (10000 * 0.4),
        "in_ca": True,
    }
    request = Request.blank('/')
    response = (line.strip() for line in
                mustache(request=request, context=context).strip().split("\n"))
    assert tuple(response) == ('Hello Chris',
                               'You have just won 10000 dollars!',
                               'Well, 6000.0 dollars, after taxes.')
