"""
Tracing utils
"""


class TagTracer(object):
    def __init__(self):
        self._tag2proc = {}
        self._writer = None
        self.indent = 0

    def get(self, name):
        return TagTracerSub(self, (name,))

    def _format_message(self, tags, args):
        if isinstance(args[-1], dict):
            extra = args[-1]
            args = args[:-1]
        else:
            extra = {}

        content = " ".join(map(str, args))
        indent = "  " * self.indent

        lines = ["%s%s [%s]\n" % (indent, content, ":".join(tags))]

        for name, value in extra.items():
            lines.append("%s    %s: %s\n" % (indent, name, value))
        return lines

    def _processmessage(self, tags, args):
        if self._writer is not None and args:
            lines = self._format_message(tags, args)
            self._writer("".join(lines))
        try:
            self._tag2proc[tags](tags, args)
        except KeyError:
            pass

    def setwriter(self, writer):
        self._writer = writer

    def setprocessor(self, tags, processor):
        if isinstance(tags, str):
            tags = tuple(tags.split(":"))
        else:
            assert isinstance(tags, tuple)
        self._tag2proc[tags] = processor


class TagTracerSub(object):
    def __init__(self, root, tags):
        self.root = root
        self.tags = tags

    def __call__(self, *args):
        self.root._processmessage(self.tags, args)

    def get(self, name):
        return self.__class__(self.root, self.tags + (name,))
