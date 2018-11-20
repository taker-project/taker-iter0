from .names import *
from .parseutils import *


class EmptyNode:
    @classmethod
    def can_load(cls, line):
        c = next_nonspace(line)
        return c == '' or c == '#'

    def load(self, line, pos=0):
        pos = skip_spaces(line, pos)
        if pos == len(line):
            return
        if line[pos] != '#':
            raise ParseError(-1, pos, 'comment expected')
        self.comment = line[pos+1:]
        return len(line)

    def save(self, line=''):
        if line != '':
            line += ' '
        line += '#' + self.comment
        return line

    def __init__(self, parent, comment=''):
        self.parent = parent
        self.comment = comment


class VariableValue:
    def _do_validate(self):
        if self.value is None:
            return True
        return type(self.value) == self.var_type()

    def type_name(self):
        raise NotImplementedError()

    def var_type(self):
        raise NotImplementedError()

    def validate(self):
        if not self._do_validate():
            raise TypeError('{} contains an invalid value'
                            .format(type(self).__name__))

    def _do_load(self, line, pos=0):
        raise NotImplementedError()

    def load(self, line, pos=0):
        new_pos, word = extract_word(line, pos)
        if word == 'null':
            self.value = None
            return new_pos
        return self._do_load(line, pos)

    def _do_save(self):
        return str(self.value)

    def save(self):
        self.validate()
        if self.value is None:
            return 'null'
        return self._do_save()

    def __init__(self, value=None):
        self.value = value


class NumberValue(VariableValue):
    def _do_load(self, line, pos=0):
        pos, word = extract_word(line, pos)
        try:
            self.value = self.var_type()(word)
            self.validate()
        except TypeError:
            raise ParseError(-1, pos, '{} expected, {} found'
                             .format(self.var_type().__name__,
                                     word))
        return pos


class IntValue(NumberValue):
    def var_type(self):
        return int

    def type_name(self):
        return 'int'

    def _do_validate(self):
        if type(self.value) is int:
            return INT_MIN <= self.value and self.value <= INT_MAX
        else:
            return super()._do_validate()


class FloatValue(NumberValue):
    def var_type(self):
        return float

    def type_name(self):
        return 'float'


class BoolValue(VariableValue):
    def var_type(self):
        return bool

    def type_name(self):
        return 'bool'

    def _do_load(self, line, pos=0):
        pos, word = extract_word(line, pos)
        if word == 'true':
            self.value = True
            return
        if word == 'false':
            self.value = False
            return
        raise ParseError(-1, pos,
                         'expected true or false, {} found'.format(word))
        return pos

    def _do_save(self):
        return 'true' if self.value else 'false'


class StrValue(VariableValue):
    def var_type(self):
        return str

    def type_name(self):
        return 'string'

    def _do_load(self, line, pos=0):
        pos, self.value = extract_string(line, pos)
        return pos

    def _do_save(self):
        return repr(self.value)


class CharValue(StrValue):
    def _do_validate(self):
        if type(self.value) is str and len(self.value) != 1:
            return False
        return super()._do_validate()

    def type_name(self):
        return 'char'

    def _do_load(self, line, pos=0):
        pos = super()._do_load(line, pos)
        if len(self.value) != 1:
            raise ParseError(-1, pos,
                             'excepted one character in char type, {} found'
                             .format(len(self.value)))
        return pos


class ArrayValue(VariableValue):
    def var_type(self):
        return list

    def type_name(self):
        return self.item_value.type_name() + '[]'

    def _do_validate(self):
        if super()._do_validate():
            return True
        for item in self.value:
            self.item_value.value = item
            if not self.item_value._do_validate():
                return False
        return True

    def _do_load(self, line, pos=0):
        pos = skip_spaces(line, pos)
        pos = line_expect(line, pos, '[')
        self.value = []
        while True:
            pos = skip_spaces(line, pos)
            if pos >= len(line):
                raise ParseError(-1, pos, 'unterminated array')
            if line[pos] == ']':
                return pos + 1
            if len(self.value) != 0:
                pos = line_expect(line, pos, ',')
            pos = self.item_value.load(line, pos)
            self.value += [self.item_value.value]

    def _do_save(self):
        res = '['
        for item in self.value:
            self.item_value.value = item
            res += self.item_value.save() + ', '
        return res[:-2] + ']'

    def __init__(self, item_class, value=None):
        self.item_class = item_class
        self.item_value = item_class()


class TypeBinder:
    binding = {}

    def _bind_type(self, type_class):
        type_name = type_class().type_name()
        self.binding[type_name] = type_class

    def create_value(self, type):
        # TODO: Add multi-dimensional array support (?)
        if len(type) > 2 and type[-2:] == '[]':
            return ArrayValue(self.binding[type[:-2]])
        else:
            return self.binding[type]()

    def __init__(self):
        self._bind_type(IntValue)
        self._bind_type(FloatValue)
        self._bind_type(CharValue)
        self._bind_type(BoolValue)
        self._bind_type(StrValue)


class VariableNode(EmptyNode):
    @classmethod
    def can_load(cls, line):
        return is_char_valid(next_nonspace(line))

    def load(self, line, pos=0):
        pos, self.key = extract_word(line, pos)
        if not is_var_name_valid(self.key):
            raise ParseError(-1, pos,
                             'invalid variable name: {}'.format(self.key))
        pos = skip_spaces(line, pos)
        pos = line_expect(line, pos, ':')
        pos, type_name = extract_word(line, pos, DELIM_CHARS_TYPE)
        try:
            self.value = self.parent.binder.create_value(type_name)
        except KeyError:
            raise ParseError(-1, pos, 'unknown type {}'.format(type_name))
        pos = skip_spaces(line, pos)
        pos = line_expect(line, pos, '=')
        pos = self.value.load(line, pos)
        return super().load(line, pos)

    def __init__(self, parent, key='', value='', comment=''):
        super().__init__(parent, comment)
        self.key = key
        self.value = value


class SectionNode(EmptyNode):
    @classmethod
    def can_load(cls, line):
        return next_nonspace(line) == '['

    def load(self, line, pos=0):
        pos = skip_spaces(line, pos)
        pos = line_expect(line, pos, '[')
        pos = skip_spaces(line, pos)
        pos, self.key = extract_word(line, pos)
        if not is_var_name_valid(self.key):
            raise ParseError(-1, pos,
                             'invalid section name: {}'.format(self.key))
        pos = skip_spaces(line, pos)
        pos = line_expect(line, pos, ']')
        return super().load(line, pos)

    def __init__(self, parent, key='', comment=''):
        super().__init__(parent, comment)
        self.key = key


class NodeList:
    def _do_process_node(self, node):
        pass

    def append_line(self, line):
        line_number = len(self.nodes)
        try:
            node = None
            for node_type in self.node_types:
                if node_type.can_load(line):
                    node = node_type(self)
                    break
            if node is None:
                node = self.node_types[0](self)
            node.load(line)
        except ParseError as parse_error:
            parse_error.row = line_number
            raise parse_error

    def dump(self):
        return '\n'.join(map((lambda x: x.save()), self.nodes))

    def clear(self):
        self.nodes = []

    def load_from_file(self, file_name):
        self.clear()
        for line in open(file_name, 'r'):
            self.append_line(line)

    def save_to_file(self, file_name):
        open(file_name, 'w').write(self.dump())

    def __init__(self):
        self.binder = TypeBinder()
        self.node_types = [VariableNode, EmptyNode, SectionNode]
        self.nodes = []
        self.clear()

# TODO: Test NodeList()


class TypiniSection:
    pass


class TypiniFile(NodeList):
    pass
