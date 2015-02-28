# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from collections import OrderedDict, namedtuple
from functools import partial
import json
import logging
import re
from webob import Request
from webob import Response
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
        if prefix_transformers is not None:
            self.prefix_transformers.update(**prefix_transformers)
        if suffix_transformers is not None:
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
                final_to_ = keepcalling(to_, needle=from_, haystack=path,
                                        updated_haystack=path_updated)
                if from_ in path_updated:
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
        return json.dumps(context, indent=4, check_circular=True)
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



class Route(namedtuple('RouteView', 'pattern handler')):
    @property
    def handler_name(self):
        """
        This pretty much only exists right now for the purposes of the
        repr() for a Route instance.

        Also it's pulled straight from django-debug-toolbar's function
        'debug_toolbar.utils.get_name_from_obj`
        """
        if hasattr(self.handler, '__name__'):
            name = self.handler.__name__
        elif hasattr(self.handler, '__class__') and hasattr(self.handler.__class__, '__name__'):
            name = self.handler.__class__.__name__
        else:
            name = '<unknown>'
        if hasattr(self.handler, '__module__'):
            module = self.handler.__module__
            name = '%s.%s' % (module, name)
        return name

    def __repr__(self):
        return "<blanket.Route pattern={pattern!r}, handler={name!s}>".format(
            pattern=self.pattern, name=self.handler_name,
        )


class Router(object):
    __slots__ = ('routes', 'seen_routes', 'url_generator')
    def __init__(self):
        self.routes = []
        self.seen_routes = set()
        self.url_generator = URLTransformRegistry()

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
        route_pattern = self.url_generator.make(path=path)
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
        return any(route.pattern.regex.match(item) for route in self)

    def __call__(self, request):
        for route in self:
            route_match = route.pattern.regex.match(request.path)
            if route_match:
                return route.handler(request=request)
        raise NoRouteFound("`{path}` does not match any of the given "
                      "routes: {routes!r}".format(
            path=request.path, routes=tuple(sorted(self.seen_routes))))



class ErrorHandlers(object):
    """
    A wrapper over an insertion-order-dictionary to map Exception classes
    to a renderer/handler.
    """

    __slots__ = ('viewconfigs',)

    def __init__(self):
        self.viewconfigs = OrderedDict()

    def add(self, exception_class, viewconfig):
        """
        Adds a new exception handler.

        :param Exception exception_class: the class to bind to
        :raises: LookupError
        :return:
        """
        if exception_class in self.viewconfigs.keys():
            raise LookupError("{cls!r} is already registered with an "
                             "error handler".format(cls=exception_class))
        self.viewconfigs[exception_class] = viewconfig
        return True

    def remove(self, exception_class):
        """
        Removes a given exception from those that are bound handlers.
        :param Exception exception_class: the class to bind to
        :raises: LookupError
        """
        if exception_class not in self.viewconfigs.keys():
            raise LookupError("{cls!r} is not registered as an "
                              "error handler".format(cls=exception_class))
        self.viewconfigs.pop(exception_class)
        return True

    def __contains__(self, item):
        found_subclass =  (issubclass(item, k) for k in self.viewconfigs.keys())
        return (item in self.viewconfigs.keys() or any(found_subclass))

    def __getitem__(self, item):
        if item in self.viewconfigs:
            return self.viewconfigs[item]
        # swallow so we can look for a superclass of this subclass exception
        possibles =  (k for k in self.viewconfigs.keys()
                      if issubclass(item, k))
        try:
            bestmatch = next(possibles)
            return self.viewconfigs[bestmatch]
        except StopIteration:
            raise KeyError("`{key!s} is not a subclass of any existing "
                           "error handler keys".format(key=item))

    def __repr__(self):
        classes = ', '.join(str(x.__name__) for x in self.viewconfigs.keys())
        return '<ErrorHandlers ({classes!r})>'.format(classes=classes)



class Blanket(object):
    """
    A blanket, generic approach to Doing Web Stuff that doesn't require
    decorators, special return values from your views/controlllers, and
    that kind of jazz.

    """
    __slots__ = (
        '_error_handlers',
        '_path_handlers',
    )

    def __init__(self):
        self._error_handlers = ErrorHandlers()
        self._path_handlers = PathHandlers()

    @property
    def log(self):
        """
        :rtype: logging.Logger
        """
        return logging.getLogger(__name__)

    def __call__(self, environ, start_response):
        try:
            request = Request(environ=environ, charset='utf-8')
        except Exception as exc:
            self.log.error(msg="Unable to create a `Request` instance with "
                               "the given `environ`", exc_info=1)
            return self.__error_view(exception=exc)

        try:
            matches = self.__get_view_handler(request=request)
        except Exception as exc:
            self.log.error(msg="Unable to get the view handler for this "
                               "`request` instance safely.", exc_info=1,
                           extra={'request': request})
            return self.__error_view(exception=exc, request=request)

        try:
            prepared_response = matches.handle(request=request)
        except Exception as exc:
            return self.__error_view(exception=exc, request=request)

        response = Response(body=prepared_response)
        return response(environ=environ, start_response=start_response)

    def error_handler(self, exception_class, viewconfig):
        self._error_handlers.add(exception_class=exception_class,
                                 viewconfig=viewconfig)
        return self

    def __error_view(self, exception, request=None):
        """

        :param Exception exception: The error intance we encountered
        :param webob.Request request: the request instance, if we got that far.
        :rtype: webob.Response
        """
        exception_class = exception.__class__
        if exception_class in self._error_handlers:
            viewconfig = self._error_handlers[exception_class]
        return None

    def __get_view_handler(self, request):
        """
        :param Request request: the request instance, if we got that far.
        """
        return None


application = Blanket().error_handler(exception_class=StandardError,
                                      viewconfig=None)
