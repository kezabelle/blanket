from collections import OrderedDict
import logging
from webob import Request
from webob import Response


class PathHandlers(object):
    __slots__ = ()


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
