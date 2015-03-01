# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from collections import OrderedDict, namedtuple
from functools import partial
from itertools import chain
import json
import logging
import re
from webob import Request
from webob import Response
from webob.acceptparse import MIMEAccept
from webob.compat import iteritems_


# Errors which may be raised
class NoOutputError(LookupError): pass
class NoRouteFound(ValueError): pass
class RouteExistsAlready(ValueError): pass


def keepcalling(data, **kwargs):
    """
    Given a function's return value (`data`), see if it's a callable, and if
    it is, keep trying to call it as a function until it finally returns
    something that's not a function/method.

    Basically allows:
    >>> def x():
    ...    def y():
    ...        def z():
    ...            return True
    ...        return z
    ...    return y
    >>> assert keepcalling(x) is True
    """
    while callable(data):
        data = data(**kwargs)
    return data


class TransformRegistry(object):
    """
    This could be a module level list, but that'd mean side-affects at import
    time. Ewww.
    """
    __slots__ = ('prefix_transformers', 'suffix_transformers')
    def __init__(self, prefix_transformers=None, suffix_transformers=None):
        self.prefix_transformers = {}
        self.suffix_transformers = {}
        if prefix_transformers is not None:  # noqa
            self.prefix_transformers.update(**prefix_transformers)
        if suffix_transformers is not None:  # noqa
            self.suffix_transformers.update(**suffix_transformers)

    def __repr__(self):
        return ("<blanket.TransformRegistry prefix_keys='{prefixes!s}' "
                "suffix_keys='{suffixes!s}'>".format(
            prefixes="', '".join(sorted(self.prefix_transformers.keys())),
            suffixes="', '".join(sorted(self.suffix_transformers.keys())),
        ))

    def __iter__(self):
        prefixes = iter(sorted(iteritems_(self.prefix_transformers)))
        suffixes = iter(sorted(iteritems_(self.suffix_transformers)))
        return iter((prefixes, suffixes))

    def __contains__(self, item):
        return item in self.suffix_transformers or item in self.prefix_transformers

    def __len__(self):
        return len(self.prefix_transformers) + len(self.suffix_transformers)


class RoutePattern(namedtuple('RoutePattern', 'raw regex')):
    __slots__ = ()
    def __repr__(self):
        return "<blanket.RoutePattern raw='{raw!s}', regex='{regex!s}'>".format(
            raw=self.raw, regex=self.regex.pattern,
        )


class URLTransformRegistry(object):
    def __init__(self):
        self.registry = TransformRegistry(suffix_transformers={
            '!d}': '>[0-9]+?)',
            '!year}': '>[1-9][0-9]{3})',
            '!month}': '>(0[1-9]|1[0-2]))',
            '!day}': '>(0[1-9]|[12]\d|3[01]))',
            '!f}': '>[0-9]+\.[0-9]+?)',
            '!x}': '>[0-9a-f]+?)',
            # '!color}': '>[0-9a-f]{3}|[0-9a-f]{6})',
            '!slug}': '>[a-z0-9_-]+?)',
            '!uuid}': '>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{32})',  # noqa
            '!s}': '>.+?)',
            # '}': '>.+)'s,
        }, prefix_transformers={'{': '(?P<'})

    def __repr__(self):
        return '<blanket.URLTransformRegistry registry={transformers!r}>'.format(  # noqa
            transformers=self.registry,
        )

    def make(self, path):
        """
        if any of the transform values is a function, it will be called
        and passed the `needle`, `haystack` and `updated_haystack` parameters.
        """
        path_updated = path
        for handler in self.registry:
            for from_, to_ in handler:
                if from_ in path_updated:
                    final_to_ = keepcalling(to_, needle=from_, haystack=path,
                                            updated_haystack=path_updated)
                    path_updated = path_updated.replace(from_, final_to_)
        if not path_updated.startswith('/'):
            final_path = '^/{path!s}$'.format(path=path_updated)
        else:
            final_path = '^{path!s}$'.format(path=path_updated)
        regex = re.compile(final_path, re.IGNORECASE)
        return RoutePattern(raw=path, regex=regex)


class Output(object):
    __slots__ = ('responds_with', 'responds_to')
    def __init__(self, responds_to, responds_with):
        self.responds_with = responds_with
        self.responds_to = responds_to

    def __contains__(self, item):
        return item in self.responds_to

    def __call__(self, request, context):
        response = keepcalling(self.responds_with,
                               request=request,
                               context=context)
        return response

def json_renderer(request, context):
    try:
        return json.dumps(context, indent=4, check_circular=True).encode('UTF-8')
    except (TypeError, ValueError) as e:
        return None

JSON = Output(responds_to=('application/json', 'application/javascript'),
              responds_with=json_renderer)


try:
    import chevron
    def mustache_template_renderer(request, context):
        render = partial(chevron.render, data=context)
        if 'template_file' in context:
            with open(context['template_file'], 'r') as template:
                return render(template=template)
        elif 'template' in context:
            return render(template=context['template'])
        return None
except ImportError:
    def mustache_template_renderer(*args, **kwargs):
        raise NoOutputError("`chevron` must be installed to use the default "
                            "`mustache` implementation")

mustache = Output(responds_to=('text/html',),
                  responds_with=mustache_template_renderer)


def get_name_from_obj(obj):
    """
    This pretty much only exists right now for the purposes of the
    repr() for a Route instance's handler.

    Also it's pulled straight from django-debug-toolbar's function
    'debug_toolbar.utils.get_name_from_obj`
        """
    if hasattr(obj, '__name__'):
        name = obj.__name__
    elif hasattr(obj, '__class__') and hasattr(obj.__class__, '__name__'):
        name = obj.__class__.__name__
    else:
        name = '<unknown>'
    if hasattr(obj, '__module__'):
        module = obj.__module__
        name = '%s.%s' % (module, name)
    return name


class Route(namedtuple('Route', 'pattern handler')):
    def handles(self, value):
        return self.pattern.regex.match(value)

    def __repr__(self):
        return "<blanket.{cls!s} pattern={pattern!r}, handler={name!s}>".format(
            pattern=self.pattern, name=get_name_from_obj(self.handler),
            cls=self.__class__.__name__,
        )


class Router(object):
    __slots__ = ('routes', 'seen_routes', 'transformer')
    def __init__(self):
        self.routes = []
        self.seen_routes = set()
        self.transformer = URLTransformRegistry()

    def __repr__(self):
        top3 = self.routes[0:3]
        remaining = len(self.routes) - len(top3)
        if remaining:
            trailing = ', {} remaining ...'.format(remaining)
        else:
            trailing = ''
        return '<blanket.Router routes={routes!r}{trailing!s}>'.format(
            routes=top3, trailing=trailing)

    def add(self, path, handler):
        route_pattern = self.transformer.make(path=path)
        # handle duplicate mount points ...
        if route_pattern.raw in self.seen_routes:
            raise RouteExistsAlready("`{path!s}` has already been added to "
                                     "this <blanket.Router>".format(
                                         path=route_pattern.raw))
        self.seen_routes.add(route_pattern.raw)
        route = Route(pattern=route_pattern, handler=handler)
        self.routes.append(route)

    def __iter__(self):
        return iter(self.routes)

    def __contains__(self, item):
        return any(route.handles(value=item) for route in self)

    def __call__(self, request):
        for route in self:
            if route.handles(value=request.path):
                return keepcalling(route.handler, request=request)
        raise NoRouteFound("`{path}` does not match any of the given "
                      "routes: {routes!r}".format(
            path=request.path, routes=tuple(sorted(self.seen_routes))))


class ErrorRoute(namedtuple('Route', 'exception_class handler')):
    def handles(self, value):
        """
        Accepts an exception instance
        """
        return isinstance(value, self.exception_class)

    def __repr__(self):
        return "<blanket.{cls!s} exception={exc!r}, handler={name!s}>".format(
            exc=self.exception_class, name=get_name_from_obj(self.handler),
            cls=self.__class__.__name__,
        )


class ErrorRouter(object):
    def __init__(self):
        self.routes = []
        self.seen_routes = set()

    def add(self, exception_class, handler):
        if exception_class in self.seen_routes:
            raise RouteExistsAlready("{exc!r} has already been added to "
                                     "this <blanket.ErrorRouter>".format(
                                         exc=exception_class,
            ))
        self.seen_routes.add(exception_class)
        route = ErrorRoute(exception_class=exception_class, handler=handler)
        self.routes.append(route)

    def __iter__(self):
        return iter(self.routes)

    def __call__(self, exception, request=None):
        for route in self:
            if route.handles(value=exception):
                return keepcalling(route.handler, exception=exception,
                                   request=request)
        raise NoRouteFound("`{exc!r}` does not match any of the given "
                      "routes: {routes!r}".format(
            exc=exception.__class__, routes=tuple(sorted(self.seen_routes))))

class ViewConfig(object):
    """

    usage is:

        vc = ViewConfig(
            parameters={
                'id': to_uuid,
                'path': to_pathlib_obj,
            }
            views=(function,),
            outputs=(JSON, HTML)
        )

    """
    __slots__ = ('parameters', 'views', 'renderers')
    def __init__(self, views, outputs, parameters=None):
        """
        :param dict parameters: converters for any URL arguments.
        :param tuple views: lit of views which do ... something.
        :param tuple outputs: list of renderers that may act on the views
        """
        self.parameters = parameters
        self.views = views
        self.renderers = outputs

    def resolved_parameters(self, request, *args, **kwargs):
        return {}

    def context(self, request, *args, **kwargs):
        """
        runs all views, and squashes their individual context dictionaries
        into one. Later views whose keys are already in the dict will replace
        the previous values.

        :rtype: dict
        """
        contexts = (view(request, *args, **kwargs) for view in self.views)
        context = ((key, dict_[key]) for dict_ in contexts
                   for key in dict_)
        return dict(context)

    def renderer(self, request, *args, **kwargs):
        accepts = request.accept
        """:type: webob.acceptparse.MIMEAccept"""
        defined_content_types = tuple(chain.from_iterable(
            renderer.responds_to for renderer in self.renderers))
        best_match = accepts.best_match(offers=defined_content_types)
        if best_match is None:
            raise NoOutputError("Unable to find a renderer given {accepts!r} "
                                "and defined renderers {renderers!r}".format(
                accepts=accepts, renderers=defined_content_types
            ))
        pick_renderer = (renderer for renderer in self.renderers
                         if best_match in renderer)
        return next(pick_renderer)

    def __call__(self, request, *args, **kwargs):
        params = self.resolved_parameters(request, *args, **kwargs)
        context = self.context(request, *args, **kwargs)
        renderer = self.renderer(request, *args, **kwargs)
        return renderer(request=request, context=context)

    def remove(self):
        return None


class Blanket(object):
    """
    A blanket, generic approach to Doing Web Stuff that doesn't require
    decorators, special return values from your views/controlllers, and
    that kind of jazz.

    Your context is your response.
    """
    __slots__ = (
        'error_router',
        'router',
    )

    def __init__(self):
        self.error_router = ErrorRouter()
        self.router = Router()

    @property
    def log(self):
        """
        :rtype: logging.Logger
        """
        return logging.getLogger(__name__)

    def get_response(self, environ):
        try:
            request = Request(environ=environ, charset='utf-8')
        except Exception as exc:
            self.log.error(msg="Unable to create a `Request` instance with "
                               "the given `environ`", exc_info=1)
            response = self.error_router(exception=exc)
        else:
            # we made the request OK
            try:
                response = self.router(request=request)
            except Exception as exc:
                self.log.error(msg="Unable to get the view handler for this "
                                   "`request` instance safely.", exc_info=1,
                               extra={'request': request})
                response = self.error_router(exception=exc, request=request)
        return Response(body=response)

    def __call__(self, environ, start_response):
        response_instance = self.get_response(environ=environ)
        return response_instance(environ=environ, start_response=start_response)
