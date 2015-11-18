
import debug

class Error(BaseException):
    def __init__(self, msg=None, data=None, tag=None):
        self.msg = msg
        self.data = data
        if not tag and hasattr(data, 'tag'):
            self.tag = data.tag
        else:
            self.tag = tag

    def get_msg(self):
        return self.msg if self.msg else 'no message'

    def __str__(self):
        msg = self.msg
        if self.data:
            try:
                msg += ' ' + self.data.sexpr()
            except:
                msg += ' ' + str(self.data)

        if self.tag:
            return debug.describe_tag(self.tag) + ': error: ' + msg + '\n' + \
                debug.point_to_tag(self.tag)
        else:
            return 'error: ' + msg

    def sexpr(self):
        return '#error'

def gen(clazz=Error, msg=None, data=None, tag=None):
    err = clazz()
    err.msg = msg
    err.data = data
    err.tag = tag
    if not tag and hasattr(data, 'tag'):
        err.tag = data.tag
    return err
